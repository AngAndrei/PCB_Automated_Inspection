import { useCallback, useEffect, useRef, useState } from "react";
import { Expand, Minus, Plus, Eye, EyeOff, ScanLine } from "lucide-react";
import { colors, type Defect, type BoardImage } from "./api";
import {
  ellipse,
  fitTransform,
  imagePoint,
  zoomAt,
  type Transform,
} from "./geometry";

interface Props {
  image: BoardImage | null;
  defects: Defect[];
  selected: string | null;
  onSelect: (id: string | null) => void;
  opacity: number;
  onOpacity: (value: number) => void;
  busy: boolean;
}

export function Viewer({
  image,
  defects,
  selected,
  onSelect,
  opacity,
  onOpacity,
  busy,
}: Props) {
  const container = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const loadedImage = useRef<HTMLImageElement | null>(null);
  const drag = useRef<{
    x: number;
    y: number;
    t: Transform;
    moved: boolean;
  } | null>(null);
  const [size, setSize] = useState({ width: 800, height: 520 });
  const [transform, setTransform] = useState<Transform>({
    scale: 1,
    x: 0,
    y: 0,
  });
  const [overlays, setOverlays] = useState(true);
  const [boxes, setBoxes] = useState(false);
  const [imageReady, setImageReady] = useState(false);
  const [imageError, setImageError] = useState(false);

  const fit = useCallback(() => {
    if (image)
      setTransform(
        fitTransform(
          image.width,
          image.height,
          size.width - 48,
          size.height - 48,
        ),
      );
  }, [image, size]);

  useEffect(() => {
    if (!container.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) setSize({ width, height });
    });
    observer.observe(container.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    loadedImage.current = null;
    setImageReady(false);
    setImageError(false);
    if (!image) return;
    const source = new Image();
    let alive = true;
    source.onload = () => {
      if (alive) {
        loadedImage.current = source;
        setImageReady(true);
      }
    };
    source.onerror = () => {
      if (alive) setImageError(true);
    };
    source.src = image.url;
    return () => {
      alive = false;
    };
  }, [image?.image_id, image?.url]);

  useEffect(fit, [fit]);

  useEffect(() => {
    const target = canvas.current;
    if (!target || !imageReady || !loadedImage.current) return;
    const ratio = window.devicePixelRatio || 1;
    target.width = Math.round(size.width * ratio);
    target.height = Math.round(size.height * ratio);
    const ctx = target.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.clearRect(0, 0, size.width, size.height);
    ctx.save();
    ctx.translate(transform.x + 24, transform.y + 24);
    ctx.scale(transform.scale, transform.scale);
    ctx.imageSmoothingEnabled = transform.scale < 2;
    ctx.drawImage(loadedImage.current, 0, 0);
    if (overlays)
      defects.forEach((defect, index) => {
        const e = ellipse(defect.bbox_xyxy);
        const active = defect.defect_id === selected;
        ctx.fillStyle = colors[defect.class_id];
        ctx.globalAlpha = opacity;
        ctx.beginPath();
        ctx.ellipse(e.cx, e.cy, e.rx, e.ry, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.lineWidth = (active ? 2 : 1) / transform.scale;
        ctx.strokeStyle = active ? "#ffffff" : colors[defect.class_id];
        if (active || Math.max(e.rx, e.ry) * transform.scale < 8) {
          ctx.beginPath();
          ctx.ellipse(
            e.cx,
            e.cy,
            Math.max(e.rx, 9 / transform.scale),
            Math.max(e.ry, 9 / transform.scale),
            0,
            0,
            Math.PI * 2,
          );
          ctx.stroke();
        }
        if (boxes)
          ctx.strokeRect(
            defect.bbox_xyxy[0],
            defect.bbox_xyxy[1],
            e.rx * 2,
            e.ry * 2,
          );
        if (active) {
          ctx.font = `${11 / transform.scale}px Consolas, monospace`;
          ctx.fillStyle = "#ffffff";
          ctx.fillText(
            String(index + 1).padStart(2, "0"),
            e.cx + e.rx + 5 / transform.scale,
            e.cy,
          );
        }
      });
    ctx.restore();
  }, [
    defects,
    imageReady,
    opacity,
    overlays,
    boxes,
    selected,
    size,
    transform,
  ]);

  useEffect(() => {
    const target = canvas.current;
    if (!target) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = target.getBoundingClientRect();
      setTransform((t) =>
        zoomAt(
          t,
          event.clientX - rect.left - 24,
          event.clientY - rect.top - 24,
          Math.exp(-event.deltaY * 0.0015),
        ),
      );
    };
    target.addEventListener("wheel", wheel, { passive: false });
    return () => target.removeEventListener("wheel", wheel);
  }, [imageReady]);

  function focusDefect(id: string | null) {
    onSelect(id);
    const defect = defects.find((d) => d.defect_id === id);
    if (defect && image) {
      const e = ellipse(defect.bbox_xyxy);
      setTransform((t) => ({
        scale: t.scale,
        x: size.width / 2 - 24 - e.cx * t.scale,
        y: size.height / 2 - 24 - e.cy * t.scale,
      }));
    }
  }

  useEffect(() => {
    if (selected) focusDefect(selected);
    // Recenter only when the selected instance changes, preserving user pan/zoom.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  return (
    <section className="viewer-panel" aria-label="PCB image viewer">
      <div className="viewer-toolbar">
        <div className="viewer-filename">
          <ScanLine size={16} />
          <span>{image?.original_name ?? "Inspection canvas"}</span>
          {image && (
            <span className="mono dimensions">
              {image.width} × {image.height}
            </span>
          )}
        </div>
        <div className="tool-group">
          <button
            className="icon-button"
            title="Zoom out"
            aria-label="Zoom out"
            disabled={!image}
            onClick={() =>
              setTransform((t) =>
                zoomAt(t, size.width / 2 - 24, size.height / 2 - 24, 0.8),
              )
            }
          >
            <Minus size={16} />
          </button>
          <span className="zoom mono">
            {image ? `${Math.round(transform.scale * 100)}%` : "—"}
          </span>
          <button
            className="icon-button"
            title="Zoom in"
            aria-label="Zoom in"
            disabled={!image}
            onClick={() =>
              setTransform((t) =>
                zoomAt(t, size.width / 2 - 24, size.height / 2 - 24, 1.25),
              )
            }
          >
            <Plus size={16} />
          </button>
          <button
            className="icon-button"
            title="Fit image (0)"
            aria-label="Fit image"
            disabled={!image}
            onClick={fit}
          >
            <Expand size={16} />
          </button>
          <span className="toolbar-divider" />
          <button
            className={`icon-button ${overlays ? "active" : ""}`}
            title="Toggle overlays"
            aria-label="Toggle overlays"
            aria-pressed={overlays}
            disabled={!image}
            onClick={() => setOverlays((v) => !v)}
          >
            {overlays ? <Eye size={17} /> : <EyeOff size={17} />}
          </button>
        </div>
      </div>
      <div
        className={`canvas-wrap ${busy ? "processing" : ""}`}
        ref={container}
      >
        {!image && (
          <div className="canvas-empty">
            <div className="board-symbol">
              <ScanLine size={40} strokeWidth={1} />
            </div>
            <span className="eyebrow">READY FOR YOUR NEXT BOARD</span>
            <h2>A closer look at every trace.</h2>
            <p>
              Upload a bare PCB image to locate and review
              <br />
              six common types of manufacturing defects.
            </p>
            <div className="canvas-formats mono">
              JPG / PNG <span>·</span> UP TO 25 MiB
            </div>
          </div>
        )}
        {image && (
          <canvas
            ref={canvas}
            className="inspection-canvas"
            style={{ width: size.width, height: size.height }}
            tabIndex={0}
            aria-label={`Inspection image: ${image.original_name}. ${defects.length} detected areas. Scroll to zoom; drag to pan.`}
            onKeyDown={(e) => {
              if (e.key === "0") fit();
              if (e.key === "Escape") onSelect(null);
              if (e.key === "+" || e.key === "=")
                setTransform((t) =>
                  zoomAt(t, size.width / 2 - 24, size.height / 2 - 24, 1.25),
                );
              if (e.key === "-")
                setTransform((t) =>
                  zoomAt(t, size.width / 2 - 24, size.height / 2 - 24, 0.8),
                );
            }}
            onPointerDown={(e) => {
              e.currentTarget.setPointerCapture(e.pointerId);
              drag.current = {
                x: e.clientX,
                y: e.clientY,
                t: transform,
                moved: false,
              };
            }}
            onPointerMove={(e) => {
              const d = drag.current;
              if (!d) return;
              const dx = e.clientX - d.x,
                dy = e.clientY - d.y;
              if (Math.abs(dx) + Math.abs(dy) > 3) d.moved = true;
              if (d.moved)
                setTransform({ ...d.t, x: d.t.x + dx, y: d.t.y + dy });
            }}
            onPointerUp={(e) => {
              const d = drag.current;
              drag.current = null;
              if (!d?.moved) {
                const rect = e.currentTarget.getBoundingClientRect();
                const [x, y] = imagePoint(
                  e.clientX - rect.left - 24,
                  e.clientY - rect.top - 24,
                  transform,
                );
                const hit = [...defects].reverse().find((defect) => {
                  const b = defect.bbox_xyxy;
                  return x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3];
                });
                onSelect(hit?.defect_id ?? null);
              }
            }}
            onPointerCancel={() => {
              drag.current = null;
            }}
          />
        )}
        {imageError && (
          <div className="canvas-message" role="alert">
            Could not load the saved image. Reopen the inspection to retry.
          </div>
        )}
        {image && !imageReady && !imageError && (
          <div className="canvas-message">Loading image…</div>
        )}
        {busy && (
          <div className="processing-badge">
            <span className="spinner" /> Inspecting board
          </div>
        )}
        <span className="canvas-corner top-left" />
        <span className="canvas-corner bottom-right" />
      </div>
      <div className="viewer-footer">
        <span className="overlay-caption">
          <i /> Approximate defect areas
        </span>
        <label className="opacity-label">
          Opacity{" "}
          <input
            aria-label="Overlay opacity"
            type="range"
            min="0"
            max="80"
            value={Math.round(opacity * 100)}
            onChange={(e) => onOpacity(Number(e.target.value) / 100)}
          />
          <span className="mono">{Math.round(opacity * 100)}%</span>
        </label>
        <label className="boxes-label">
          <input
            type="checkbox"
            checked={boxes}
            onChange={(e) => setBoxes(e.target.checked)}
          />{" "}
          Boxes
        </label>
      </div>
    </section>
  );
}
