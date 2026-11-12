"""Short SQLite transactions, durable queue and lease-guarded completion."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from .images import normalize_image


class Conflict(ValueError):
    pass


class CapacityError(ValueError):
    pass


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return uuid4().hex


def unpack(row):
    if row is None:
        raise KeyError("Record not found")
    item = dict(row)
    for key in ("model", "profile", "result", "error"):
        if key in item and item[key] is not None:
            item[key] = json.loads(item[key])
    return item


class Store:
    def __init__(self, root: Path, queue_limit=20):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "images").mkdir(exist_ok=True)
        self.database = self.root / "inspection.sqlite3"
        self.queue_limit = queue_limit
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS images (
                  image_id TEXT PRIMARY KEY, original_name TEXT NOT NULL,
                  width INTEGER NOT NULL, height INTEGER NOT NULL,
                  content_hash TEXT NOT NULL, canonical_path TEXT NOT NULL,
                  created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS inspections (
                  inspection_id TEXT PRIMARY KEY, image_id TEXT NOT NULL REFERENCES images(image_id),
                  model TEXT NOT NULL, profile TEXT NOT NULL, status TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, attempt INTEGER DEFAULT 0,
                  worker_id TEXT, lease_token TEXT, expires REAL, result TEXT, error TEXT);
                CREATE INDEX IF NOT EXISTS inspections_status ON inspections(status, created_at);
                CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, heartbeat REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS reviews (
                  review_id TEXT PRIMARY KEY, inspection_id TEXT NOT NULL REFERENCES inspections(inspection_id),
                  defect_id TEXT, verdict TEXT NOT NULL, note TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add_image(self, data, name):
        canonical = normalize_image(data)
        image_id = identifier()
        path = self.root / "images" / f"{image_id}.png"
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(canonical.png)
        temporary.replace(path)
        width, height = canonical.image.size
        with self.connect() as db:
            db.execute(
                "INSERT INTO images VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    image_id,
                    Path(name or "image.png").name[:240],
                    width,
                    height,
                    canonical.content_hash,
                    str(path),
                    timestamp(),
                ),
            )
        return self.get_image(image_id)

    def get_image(self, image_id):
        with self.connect() as db:
            return unpack(db.execute("SELECT * FROM images WHERE image_id=?", (image_id,)).fetchone())

    def enqueue(self, image_id, model, profile):
        inspection_id = identifier()
        self.get_image(image_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM inspections WHERE status='queued'").fetchone()[0]
            if count >= self.queue_limit:
                raise CapacityError("Queue is full. Wait for an inspection to finish.")
            now = timestamp()
            db.execute(
                """INSERT INTO inspections
                (inspection_id,image_id,model,profile,status,created_at,updated_at)
                VALUES (?,?,?,?,'queued',?,?)""",
                (inspection_id, image_id, json.dumps(model), json.dumps(profile), now, now),
            )
        return self.get_job(inspection_id)

    def get_job(self, inspection_id):
        with self.connect() as db:
            return unpack(
                db.execute(
                    "SELECT * FROM inspections WHERE inspection_id=?", (inspection_id,)
                ).fetchone()
            )

    def history(self, limit=30, offset=0):
        with self.connect() as db:
            rows = db.execute(
                """SELECT inspections.*, images.original_name, images.width, images.height
                FROM inspections JOIN images USING(image_id)
                ORDER BY inspections.created_at DESC LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            total = db.execute("SELECT count(*) FROM inspections").fetchone()[0]
            return {
                "items": [unpack(row) for row in rows],
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    def claim(self, worker_id, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM inspections WHERE status='running' AND expires>=? LIMIT 1", (now,)
            ).fetchone():
                return None
            row = db.execute(
                "SELECT * FROM inspections WHERE status='queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            token = identifier()
            db.execute(
                """UPDATE inspections SET status='running', worker_id=?, lease_token=?,
                expires=?, attempt=attempt+1, updated_at=?, error=NULL WHERE inspection_id=?""",
                (worker_id, token, now + 60, timestamp(), row["inspection_id"]),
            )
            return unpack(
                db.execute(
                    "SELECT * FROM inspections WHERE inspection_id=?", (row["inspection_id"],)
                ).fetchone()
            )

    def heartbeat(self, lease, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            return (
                db.execute(
                    """UPDATE inspections SET expires=? WHERE inspection_id=?
                AND status='running' AND lease_token=? AND expires>=?""",
                    (now + 60, lease["inspection_id"], lease["lease_token"], now),
                ).rowcount
                == 1
            )

    def worker_heartbeat(self, worker_id):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO workers VALUES (?,?)", (worker_id, time.time()))

    def worker_ready(self):
        with self.connect() as db:
            return (
                db.execute(
                    "SELECT count(*) FROM workers WHERE heartbeat>?", (time.time() - 20,)
                ).fetchone()[0]
                > 0
            )

    def expire(self, now=None):
        now = time.time() if now is None else now
        error = json.dumps(
            {"code": "WORKER_LOST", "message": "Worker stopped responding. Retry this inspection."}
        )
        with self.connect() as db:
            return db.execute(
                """UPDATE inspections SET status='failed', error=?, updated_at=?
                WHERE status='running' AND expires<?""",
                (error, timestamp(), now),
            ).rowcount

    def finish(self, lease, result, now=None):
        self._finalize(lease, "completed", result, None, now)

    def fail(self, lease, code, message):
        self._finalize(lease, "failed", None, {"code": code, "message": message})

    def _finalize(self, lease, status, result, error, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            updated = db.execute(
                """UPDATE inspections SET status=?, result=?, error=?, updated_at=?
                WHERE inspection_id=? AND status='running' AND lease_token=? AND expires>=?""",
                (
                    status,
                    json.dumps(result) if result is not None else None,
                    json.dumps(error) if error else None,
                    timestamp(),
                    lease["inspection_id"],
                    lease["lease_token"],
                    now,
                ),
            ).rowcount
            if updated != 1:
                raise Conflict("This attempt no longer owns the inspection.")

    def cancel(self, inspection_id):
        self._transition(inspection_id, "queued", "cancelled")

    def retry(self, inspection_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("SELECT count(*) FROM inspections WHERE status='queued'").fetchone()[0]
                >= self.queue_limit
            ):
                raise CapacityError("Queue is full.")
            changed = db.execute(
                """UPDATE inspections SET status='queued', error=NULL, lease_token=NULL,
                expires=NULL, updated_at=? WHERE inspection_id=? AND status='failed'""",
                (timestamp(), inspection_id),
            ).rowcount
            if changed != 1:
                raise Conflict("Only failed inspections can be retried.")

    def _transition(self, inspection_id, before, after):
        with self.connect() as db:
            changed = db.execute(
                "UPDATE inspections SET status=?, updated_at=? WHERE inspection_id=? AND status=?",
                (after, timestamp(), inspection_id, before),
            ).rowcount
            if changed != 1:
                raise Conflict(f"This action requires a {before} inspection.")

    def review(self, inspection_id, defect_id, verdict, note):
        row = self.get_job(inspection_id)
        if row["status"] != "completed":
            raise Conflict("Review is available after the inspection completes.")
        if verdict not in {"confirmed", "rejected", "uncertain", "missed"}:
            raise ValueError("Unknown review verdict")
        if defect_id and not any(d["defect_id"] == defect_id for d in row["result"]["defects"]):
            raise ValueError("Defect does not belong to this inspection")
        event = {
            "review_id": identifier(),
            "inspection_id": inspection_id,
            "defect_id": defect_id,
            "verdict": verdict,
            "note": note[:2000],
            "created_at": timestamp(),
        }
        with self.connect() as db:
            db.execute("INSERT INTO reviews VALUES (?,?,?,?,?,?)", tuple(event.values()))
        return event

    def reviews(self, inspection_id):
        with self.connect() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM reviews WHERE inspection_id=? ORDER BY created_at", (inspection_id,)
                ).fetchall()
            ]
