import { useEffect, useRef, useState } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronRight,
  CircleHelp,
  CircuitBoard,
  Clock3,
  Cpu,
  FolderOpen,
  History as HistoryIcon,
  Layers3,
  LoaderCircle,
  Play,
  Plus,
  RotateCcw,
  ScanLine,
  ShieldCheck,
  Upload,
  X,
} from "lucide-react";
import {
  api,
  post,
  pretty,
  colors,
  classNames,
  type BoardImage,
  type Model,
  type Health,
  type History,
  type Inspection,
  type Review,
} from "./api";
import { Viewer } from "./Viewer";

const date = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
const label = (job: Inspection) =>
  job.status === "completed"
    ? pretty(job.result!.decision)
    : pretty(job.status);

export default function App() {
  const [tab, setTab] = useState<"inspect" | "history" | "models">("inspect");
  const [models, setModels] = useState<Model[]>([]);
  const [modelErrors, setModelErrors] = useState<string[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [modelId, setModelId] = useState("");
  const [profileId, setProfileId] = useState("quality-v1");
  const [image, setImage] = useState<BoardImage | null>(null);
  const [job, setJob] = useState<Inspection | null>(null);
  const [history, setHistory] = useState<History>({ items: [], total: 0 });
  const [selected, setSelected] = useState<string | null>(null);
  const [opacity, setOpacity] = useState(0.4);
  const [filter, setFilter] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [dragging, setDragging] = useState(false);
  const [help, setHelp] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const selectionVersion = useRef(0);
  const activeOperations = useRef(0);
  function beginOperation() {
    activeOperations.current += 1;
    setBusy(true);
  }
  function endOperation() {
    activeOperations.current -= 1;
    setBusy(activeOperations.current > 0);
  }
  const model = models.find((item) => item.model_id === modelId);
  const chosenProfile =
    model?.profiles.find((p) => p.profile_id === profileId) ??
    model?.profiles[0];
  const processing = job?.status === "queued" || job?.status === "running";
  const defects = job?.result?.defects ?? [];
  const visible = defects.filter((d) => d.confidence >= filter);
  const activeDefect = defects.find((d) => d.defect_id === selected);
  const selectedReview = [...(job?.reviews ?? [])]
    .reverse()
    .find((r) => r.defect_id === selected);

  async function refresh() {
    try {
      const [h, m, recent] = await Promise.all([
        api<Health>("/health"),
        api<{ items: Model[]; errors: string[] }>("/models"),
        api<History>("/inspections"),
      ]);
      setHealth(h);
      setModels(m.items);
      setModelErrors(m.errors);
      setHistory(recent);
      setModelId((current) =>
        m.items.some((item) => item.model_id === current)
          ? current
          : (m.items[0]?.model_id ?? ""),
      );
    } catch {
      setHealth(null);
    }
  }
  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), 10000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    setNote("");
  }, [selected, job?.inspection_id]);
  useEffect(() => {
    if (!processing || !job) return;
    let alive = true;
    const poll = async () => {
      try {
        const current = await api<Inspection>(
          `/inspections/${job.inspection_id}`,
        );
        if (alive) {
          setJob((previous) =>
            previous?.inspection_id === current.inspection_id
              ? current
              : previous,
          );
          if (current.status !== "queued" && current.status !== "running")
            void refresh();
        }
      } catch (err) {
        if (alive) setError((err as Error).message);
      }
    };
    const timer = setInterval(() => void poll(), 1000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [job?.inspection_id, processing]);

  async function upload(file?: File) {
    if (!file || busy || processing) return;
    const version = ++selectionVersion.current;
    beginOperation();
    setError("");
    try {
      const data = new FormData();
      data.append("file", file);
      const uploaded = await api<BoardImage>("/images", {
        method: "POST",
        body: data,
      });
      if (version !== selectionVersion.current) return;
      setImage(uploaded);
      setJob(null);
      setSelected(null);
      setFilter(0);
      setTab("inspect");
    } catch (err) {
      if (version === selectionVersion.current)
        setError((err as Error).message);
    } finally {
      endOperation();
      if (fileInput.current) fileInput.current.value = "";
    }
  }
  async function inspect() {
    if (!image || !model || !chosenProfile) return;
    const version = ++selectionVersion.current;
    beginOperation();
    setError("");
    setSelected(null);
    setFilter(0);
    try {
      const created = await post<Inspection>("/inspections", {
        image_id: image.image_id,
        model_id: modelId,
        profile_id: chosenProfile.profile_id,
      });
      if (version === selectionVersion.current) setJob(created);
    } catch (err) {
      if (version === selectionVersion.current)
        setError((err as Error).message);
    } finally {
      endOperation();
    }
  }
  async function action(name: "cancel" | "retry") {
    if (!job) return;
    const version = selectionVersion.current;
    const recordId = job.inspection_id;
    beginOperation();
    setError("");
    try {
      const updated = await post<Inspection>(
        `/inspections/${recordId}/${name}`,
      );
      if (version === selectionVersion.current)
        setJob((current) =>
          current?.inspection_id === recordId ? updated : current,
        );
      void refresh();
    } catch (err) {
      if (version === selectionVersion.current)
        setError((err as Error).message);
    } finally {
      endOperation();
    }
  }
  async function review(verdict: string, defectId: string | null = selected) {
    if (!job) return;
    const version = selectionVersion.current;
    const recordId = job.inspection_id;
    beginOperation();
    setError("");
    try {
      const event = await post<Review>(`/inspections/${recordId}/reviews`, {
        defect_id: defectId,
        verdict,
        note,
      });
      if (version !== selectionVersion.current) return;
      setJob((current) =>
        current?.inspection_id === recordId &&
        !current.reviews.some((r) => r.review_id === event.review_id)
          ? { ...current, reviews: [...current.reviews, event] }
          : current,
      );
      setNote("");
    } catch (err) {
      if (version === selectionVersion.current)
        setError((err as Error).message);
    } finally {
      endOperation();
    }
  }
  async function open(item: Inspection) {
    const version = ++selectionVersion.current;
    beginOperation();
    setError("");
    try {
      const current = await api<Inspection>(
        `/inspections/${item.inspection_id}`,
      );
      if (version !== selectionVersion.current) return;
      setImage(current.image);
      setJob(current);
      setSelected(null);
      setFilter(0);
      setTab("inspect");
    } catch (err) {
      if (version === selectionVersion.current)
        setError((err as Error).message);
    } finally {
      endOperation();
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("inspect");
          }}
          aria-label="Circuit Inspect home"
        >
          <span className="brand-mark">
            <CircuitBoard size={25} strokeWidth={1.7} />
          </span>
          <span>
            CIRCUIT
            <span className="brand-second">
              INSPECT<span className="brand-dot">.</span>
            </span>
          </span>
        </a>
        <div className="sidebar-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <button
            className={tab === "inspect" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("inspect")}
          >
            <ScanLine size={18} /> Inspection <ChevronRight size={14} />
          </button>
          <button
            className={tab === "history" ? "nav-item active" : "nav-item"}
            onClick={() => {
              setTab("history");
              void refresh();
            }}
          >
            <HistoryIcon size={18} /> History{" "}
            <span className="nav-count mono">{history.total}</span>
          </button>
          <button
            className={tab === "models" ? "nav-item active" : "nav-item"}
            onClick={() => setTab("models")}
          >
            <Cpu size={18} /> Models{" "}
            <span className="nav-count mono">{models.length}</span>
          </button>
        </nav>
        <div className="sidebar-spacer" />
        <div className="local-card">
          <ShieldCheck size={19} />
          <div>
            <strong>Local by design</strong>
            <p>
              Your board images stay
              <br />
              on this machine.
            </p>
          </div>
        </div>
        <button className="help-link" onClick={() => setHelp((v) => !v)}>
          <CircleHelp size={16} /> Inspection guide <ArrowRight size={14} />
        </button>
        <div className="sidebar-bottom">
          <span className="mono">PCB VISION LAB</span>
          <span className="mono">v0.1</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={12} />
            <strong>{tab === "inspect" ? "Inspection" : pretty(tab)}</strong>
          </div>
          <div className="system-state">
            <span
              className={`status-dot ${health?.worker_ready ? "online" : ""}`}
            />
            {!health
              ? "Connecting to service"
              : health.worker_ready
                ? "Worker online"
                : "Worker offline"}
            <span className="mono local-label">LOCAL</span>
          </div>
        </header>
        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">AUTOMATED OPTICAL INSPECTION</div>
              <h1>
                {tab === "inspect"
                  ? "Board inspection"
                  : tab === "history"
                    ? "Inspection history"
                    : "Model registry"}
              </h1>
              <p>
                {tab === "inspect"
                  ? "Locate defects. Review the details. Keep a traceable record."
                  : tab === "history"
                    ? "Every inspection, with its original model and review history."
                    : "Versioned PCB detectors, inference profiles, and measured results."}
              </p>
            </div>
            {tab !== "inspect" && (
              <button
                className="button primary"
                onClick={() => {
                  setTab("inspect");
                  fileInput.current?.click();
                }}
              >
                <Plus size={16} /> New inspection
              </button>
            )}
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {help && (
            <div className="guide">
              <strong>Start with a bare PCB image.</strong>
              <p>
                Upload a JPG or PNG, choose an installed PCB model, and run an
                inspection. Select any colored region to review the finding.
                Scroll to zoom and drag to pan; press 0 to fit the image. The
                overlays show approximate locations. Results apply to visible
                defects in the model’s training domain.
              </p>
              <button className="text-button" onClick={() => setHelp(false)}>
                Close guide
              </button>
            </div>
          )}
          <input
            className="visually-hidden"
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,.jpg,.jpeg,.png"
            aria-label="Upload PCB image"
            onChange={(e) => void upload(e.target.files?.[0])}
          />
          {tab === "inspect" && (
            <>
              <section
                className={`input-bar ${dragging ? "dragging" : ""}`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  void upload(e.dataTransfer.files[0]);
                }}
              >
                <button
                  className="upload-control"
                  disabled={busy || processing}
                  onClick={() => fileInput.current?.click()}
                >
                  <span className="upload-icon">
                    {busy && !job ? (
                      <LoaderCircle size={20} className="spin" />
                    ) : (
                      <Upload size={20} />
                    )}
                  </span>
                  <span>
                    <strong>
                      {image ? "Change board image" : "Upload a board image"}
                    </strong>
                    <small>
                      {image
                        ? `${image.width} × ${image.height} px · ${image.original_name}`
                        : "Drop a JPG / PNG here or browse files"}
                    </small>
                  </span>
                  <FolderOpen size={17} />
                </button>
                <div className="input-divider" />
                <label className="model-select">
                  <span className="field-label">DETECTOR</span>
                  <select
                    aria-label="Detector model"
                    disabled={processing}
                    value={modelId}
                    onChange={(e) => {
                      setModelId(e.target.value);
                      setProfileId(
                        models.find((m) => m.model_id === e.target.value)
                          ?.profiles[0]?.profile_id ?? "quality-v1",
                      );
                    }}
                  >
                    <option value="" disabled>
                      No PCB model installed
                    </option>
                    {models.map((m) => (
                      <option key={m.model_id} value={m.model_id}>
                        {m.label ?? m.model_id}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="profile-select">
                  <span className="field-label">PROFILE</span>
                  <select
                    aria-label="Inference profile"
                    disabled={!model || processing}
                    value={chosenProfile?.profile_id ?? ""}
                    onChange={(e) => setProfileId(e.target.value)}
                  >
                    {model?.profiles.map((p) => (
                      <option key={p.profile_id} value={p.profile_id}>
                        {p.profile_id}
                      </option>
                    )) ?? <option>quality-v1</option>}
                  </select>
                </label>
                <button
                  className="button primary run-button"
                  disabled={
                    !image ||
                    !model ||
                    !health?.worker_ready ||
                    busy ||
                    processing
                  }
                  onClick={() => void inspect()}
                >
                  {processing || busy ? (
                    <LoaderCircle size={16} className="spin" />
                  ) : (
                    <Play size={15} fill="currentColor" />
                  )}
                  {processing ? "Inspecting…" : "Run inspection"}
                </button>
              </section>
              {health && !health.model_ready && (
                <div className="setup-notice">
                  <Cpu size={16} />
                  <span>
                    No PCB model installed. Prepare the dataset and train a
                    detector to enable inspection.
                  </span>
                  <button onClick={() => setTab("models")}>
                    View setup <ArrowRight size={13} />
                  </button>
                </div>
              )}
              {model &&
                ["development", "unvalidated"].includes(
                  model.training_status ?? "unvalidated",
                ) && (
                  <div className="setup-notice" role="status">
                    <Cpu size={16} />
                    <span>
                      Unvalidated model: accuracy is not established. All
                      results require manual review.
                    </span>
                    <button onClick={() => setTab("models")}>
                      View measured results <ArrowRight size={13} />
                    </button>
                  </div>
                )}
              <div className="inspection-layout">
                <div className="viewer-column">
                  <Viewer
                    image={image}
                    defects={visible}
                    selected={selected}
                    onSelect={setSelected}
                    opacity={opacity}
                    onOpacity={setOpacity}
                    busy={!!processing}
                  />
                  <div className="inspection-meta">
                    <span>
                      <Layers3 size={14} />{" "}
                      {job ? job.model.model_id : "No inspection started"}
                    </span>
                    <span>
                      <Clock3 size={14} />{" "}
                      {job?.result
                        ? `${(job.result.timings_ms.total / 1000).toFixed(2)} s total`
                        : "Timing available after inspection"}
                    </span>
                    {job && (
                      <span className="mono">
                        #{job.inspection_id.slice(0, 8)}
                      </span>
                    )}
                  </div>
                  {!!job?.result?.warnings.length && (
                    <div className="warning-banner">
                      {job.result.warnings.map((w) => (
                        <p key={w}>{w}</p>
                      ))}
                    </div>
                  )}
                  <div className="class-legend">
                    {classNames.map((name, i) => (
                      <span key={name}>
                        <i style={{ background: colors[i] }} />
                        {pretty(name)}
                      </span>
                    ))}
                  </div>
                </div>
                <aside
                  className="results-panel"
                  aria-label="Inspection results"
                >
                  <div className="results-heading">
                    <h2>Findings</h2>
                    <span className="count-badge mono">
                      {job?.result
                        ? String(defects.length).padStart(2, "0")
                        : "—"}
                    </span>
                  </div>
                  {job && (
                    <div
                      className={`decision ${job.status === "failed" ? "failed" : (job.result?.decision ?? job.status)}`}
                    >
                      <span className="status-dot" />
                      {label(job)}
                    </div>
                  )}
                  {job?.status === "failed" && (
                    <div className="failed-state">
                      <p>{job.error?.message}</p>
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() => void action("retry")}
                      >
                        <RotateCcw size={14} /> Retry inspection
                      </button>
                    </div>
                  )}
                  {processing && (
                    <div className="result-empty">
                      <LoaderCircle size={26} className="spin" />
                      <h3>
                        {job.status === "queued"
                          ? "Waiting for the worker"
                          : "Examining your board"}
                      </h3>
                      <p>
                        Results will appear here when the inspection is
                        complete.
                      </p>
                      {job.status === "queued" && (
                        <button
                          className="text-button"
                          disabled={busy}
                          onClick={() => void action("cancel")}
                        >
                          Cancel queued inspection
                        </button>
                      )}
                    </div>
                  )}
                  {!job && (
                    <div className="result-empty">
                      <Activity size={28} strokeWidth={1.2} />
                      <h3>Ready when you are</h3>
                      <p>
                        Detected areas, confidence scores, and review controls
                        will appear here.
                      </p>
                      <div className="steps">
                        <span>
                          <b>01</b> Load a board image
                        </span>
                        <span>
                          <b>02</b> Run the detector
                        </span>
                        <span>
                          <b>03</b> Review each finding
                        </span>
                      </div>
                    </div>
                  )}
                  {job?.status === "completed" && (
                    <>
                      <div className="display-filter">
                        <label htmlFor="confidence-filter">
                          Display confidence{" "}
                          <span className="mono">
                            ≥ {Math.round(filter * 100)}%
                          </span>
                        </label>
                        <input
                          id="confidence-filter"
                          type="range"
                          min="0"
                          max="100"
                          value={Math.round(filter * 100)}
                          onChange={(e) => {
                            setFilter(Number(e.target.value) / 100);
                            setSelected(null);
                          }}
                        />
                        <small>
                          {visible.length} of {defects.length} findings shown ·
                          saved result unchanged
                        </small>
                      </div>
                      {defects.length === 0 && (
                        <div className="result-empty">
                          <ShieldCheck size={28} />
                          <h3>No defects detected</h3>
                          <p>
                            No findings above this model’s operating threshold.
                            Review the image for your application.
                          </p>
                        </div>
                      )}
                      <div className="defect-list">
                        {visible.map((d, i) => {
                          const verdict = [...job.reviews]
                            .reverse()
                            .find((r) => r.defect_id === d.defect_id)?.verdict;
                          return (
                            <button
                              key={d.defect_id}
                              className={`defect-item ${selected === d.defect_id ? "selected" : ""}`}
                              onClick={() => setSelected(d.defect_id)}
                              style={
                                {
                                  "--defect-color": colors[d.class_id],
                                } as React.CSSProperties
                              }
                            >
                              <span className="defect-index mono">
                                {String(i + 1).padStart(2, "0")}
                              </span>
                              <span className="defect-description">
                                <strong>{pretty(d.class_name)}</strong>
                                <small>
                                  {verdict
                                    ? pretty(verdict)
                                    : "Awaiting review"}
                                </small>
                              </span>
                              <span className="confidence mono">
                                {Math.round(d.confidence * 100)}%
                              </span>
                              <ChevronRight size={14} />
                            </button>
                          );
                        })}
                      </div>
                      {activeDefect && (
                        <div className="review-card">
                          <div className="field-label">
                            REVIEW FINDING{" "}
                            {activeDefect.defect_id.toUpperCase()}
                          </div>
                          <p>
                            Mark your assessment independently of the model.
                          </p>
                          <label
                            className="visually-hidden"
                            htmlFor="review-note"
                          >
                            Review note
                          </label>
                          <textarea
                            id="review-note"
                            maxLength={2000}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="Optional review note…"
                          />
                          <div className="review-buttons">
                            <button
                              title="Confirm defect"
                              disabled={busy}
                              className={
                                selectedReview?.verdict === "confirmed"
                                  ? "chosen"
                                  : ""
                              }
                              onClick={() => void review("confirmed")}
                            >
                              <Check size={14} /> Confirm
                            </button>
                            <button
                              title="Reject detection"
                              disabled={busy}
                              className={
                                selectedReview?.verdict === "rejected"
                                  ? "chosen"
                                  : ""
                              }
                              onClick={() => void review("rejected")}
                            >
                              <X size={14} /> Reject
                            </button>
                            <button
                              disabled={busy}
                              className={
                                selectedReview?.verdict === "uncertain"
                                  ? "chosen"
                                  : ""
                              }
                              onClick={() => void review("uncertain")}
                            >
                              Unsure
                            </button>
                          </div>
                        </div>
                      )}
                      <div className="export-section">
                        <div className="field-label">EXPORT INSPECTION</div>
                        <div className="export-buttons">
                          <a
                            className="button secondary"
                            href={`/api/inspections/${job.inspection_id}/export?format=png&opacity=${opacity}`}
                            download
                          >
                            <ArrowDownToLine size={14} /> Overlay PNG
                          </a>
                          <a
                            className="button secondary"
                            href={`/api/inspections/${job.inspection_id}/export?format=json`}
                            download
                          >
                            <ArrowDownToLine size={14} /> JSON
                          </a>
                        </div>
                        <p>
                          PNG includes all saved findings at the selected
                          opacity.
                        </p>
                      </div>
                      <details className="missed-note">
                        <summary>Record a missed defect</summary>
                        <textarea
                          aria-label="Missed defect note"
                          value={selected ? "" : note}
                          maxLength={2000}
                          onFocus={() => setSelected(null)}
                          onChange={(e) => setNote(e.target.value)}
                          placeholder="Describe where the missed defect is…"
                        />
                        <button
                          className="button secondary"
                          disabled={busy || !note.trim() || !!selected}
                          onClick={() => void review("missed", null)}
                        >
                          Save image-level note
                        </button>
                      </details>
                    </>
                  )}
                  {job?.status === "cancelled" && (
                    <div className="result-empty">
                      <p>
                        This queued inspection was cancelled. You can start a
                        new inspection above.
                      </p>
                    </div>
                  )}
                </aside>
              </div>
            </>
          )}
          {tab === "history" && (
            <section className="history-panel">
              <div className="section-title">
                <h2>Recent inspections</h2>
                <span className="mono muted">{history.total} RECORDS</span>
              </div>
              {history.items.length === 0 ? (
                <div className="table-empty">
                  <HistoryIcon size={30} />
                  <h3>Your inspection history starts here.</h3>
                  <p>
                    Completed, failed, and queued runs will be kept with their
                    original settings.
                  </p>
                </div>
              ) : (
                <>
                  <div className="history-table">
                    <div className="history-row table-head">
                      <span>BOARD / FILE</span>
                      <span>RESULT</span>
                      <span>DETECTOR</span>
                      <span>CREATED</span>
                      <span />
                    </div>
                    {history.items.map((item) => (
                      <button
                        className="history-row"
                        key={item.inspection_id}
                        onClick={() => open(item)}
                      >
                        <span className="history-file">
                          <img src={item.image.url} alt="" />
                          <span>
                            <strong>{item.image.original_name}</strong>
                            <small className="mono">
                              #{item.inspection_id.slice(0, 8)} ·{" "}
                              {item.image.width} × {item.image.height}
                            </small>
                          </span>
                        </span>
                        <span
                          className={`history-status ${item.status === "failed" ? "failed" : (item.result?.decision ?? item.status)}`}
                        >
                          {label(item)}
                        </span>
                        <span className="mono model-cell">
                          {item.model.model_id}
                        </span>
                        <span>{date(item.created_at)}</span>
                        <ChevronRight size={16} />
                      </button>
                    ))}
                  </div>
                  {history.items.length < history.total && (
                    <button
                      className="button secondary load-more"
                      onClick={async () => {
                        try {
                          const more = await api<History>(
                            `/inspections?offset=${history.items.length}`,
                          );
                          setHistory((h) => ({
                            ...more,
                            items: [...h.items, ...more.items],
                          }));
                        } catch (err) {
                          setError((err as Error).message);
                        }
                      }}
                    >
                      Load more inspections
                    </button>
                  )}
                </>
              )}
            </section>
          )}
          {tab === "models" && (
            <div className="models-layout">
              <section className="model-panel">
                <div className="section-title">
                  <h2>Installed detectors</h2>
                  <span className="mono muted">{models.length} BUNDLES</span>
                </div>
                {models.length === 0 && (
                  <div className="table-empty">
                    <Cpu size={32} />
                    <h3>Train your first PCB detector.</h3>
                    <p>
                      The app uses a versioned model bundle trained on the six
                      supported defect categories.
                    </p>
                  </div>
                )}
                {models.map((m) => (
                  <article className="model-card" key={m.model_id}>
                    <span className="model-icon">
                      <Cpu size={24} />
                    </span>
                    <div>
                      <h3>{m.label ?? m.model_id}</h3>
                      <p className="mono">{m.model_id}</p>
                      <span className="tag">YOLO DETECTION</span>
                      <span className="tag">
                        {m.class_names.length} CLASSES
                      </span>
                      {m.training_status && (
                        <span className="tag">{m.training_status}</span>
                      )}
                      <p>Dataset: {m.dataset_version}</p>
                      <p>
                        {m.profiles
                          .map(
                            (p) =>
                              `${p.profile_id} · ${p.imgsz}px · ${p.tiled ? "tiled" : "whole image"} · ${p.device}`,
                          )
                          .join(" / ")}
                      </p>
                      {m.metrics && (
                        <details>
                          <summary>Recorded evaluation</summary>
                          <pre>{JSON.stringify(m.metrics, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  </article>
                ))}
                {modelErrors.map((err) => (
                  <div className="error-banner" key={err}>
                    {err}
                  </div>
                ))}
              </section>
              <aside className="setup-card">
                <div className="eyebrow">MODEL WORKFLOW</div>
                <h2>From data to inspection.</h2>
                <ol>
                  <li>
                    <b>Prepare</b>
                    <span>
                      Audit and split DeepPCB, then convert annotations.
                    </span>
                  </li>
                  <li>
                    <b>Train & evaluate</b>
                    <span>
                      Fine-tune YOLO and measure validation performance.
                    </span>
                  </li>
                  <li>
                    <b>Promote</b>
                    <span>
                      Install the checkpoint with its class map and checksum.
                    </span>
                  </li>
                </ol>
                <p>
                  Run the commands in the project README. Training is an offline
                  workflow; inspection uses the installed checkpoint.
                </p>
                <div className="research-note">
                  <ShieldCheck size={16} /> DeepPCB images are for research use.
                  Validate separately on real camera images.
                </div>
              </aside>
            </div>
          )}
          <footer className="page-footer">
            <span>Built for careful inspection.</span>
            <span>
              BARE PCB <i /> SIX DEFECT CLASSES <i /> LOCAL INFERENCE
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
