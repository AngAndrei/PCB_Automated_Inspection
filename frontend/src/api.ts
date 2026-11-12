import type { Box } from "./geometry";

export interface Profile {
  profile_id: string;
  confidence: number;
  tiled: boolean;
  imgsz: number;
  device: string;
}
export interface Model {
  model_id: string;
  label?: string;
  class_names: string[];
  profiles: Profile[];
  dataset_version: string;
  metrics?: Record<string, unknown>;
  training_status?: string;
}
export interface BoardImage {
  image_id: string;
  original_name: string;
  width: number;
  height: number;
  url: string;
}
export interface Defect {
  defect_id: string;
  class_id: number;
  class_name: string;
  confidence: number;
  bbox_xyxy: Box;
  localization_kind: "bbox_region";
  mask_ref: null;
}
export interface Review {
  review_id: string;
  defect_id: string | null;
  verdict: string;
  note: string;
  created_at: string;
}
export interface InspectionResult {
  decision: "defects_detected" | "no_defects_detected" | "review_needed";
  defects: Defect[];
  timings_ms: Record<string, number>;
  warnings: string[];
  tile_count?: number;
}
export interface Inspection {
  inspection_id: string;
  image_id: string;
  image: BoardImage;
  model: Model;
  profile: Profile;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  created_at: string;
  attempt: number;
  result: InspectionResult | null;
  error: { code: string; message: string } | null;
  reviews: Review[];
}
export interface Health {
  worker_ready: boolean;
  model_ready: boolean;
  status?: string;
  model_errors?: string[];
}
export interface History {
  items: Inspection[];
  total: number;
}

export const colors = [
  "#ff6b6b",
  "#f5b94e",
  "#b08cff",
  "#56cce8",
  "#53d6a0",
  "#ff8eba",
];
export const classNames = [
  "open_circuit",
  "short_circuit",
  "mouse_bite",
  "spur",
  "spurious_copper",
  "pin_hole",
];
export const pretty = (name: string) =>
  name.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status}).`,
    );
  }
  return response.json();
}
export const post = <T>(path: string, value?: unknown) =>
  api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value ?? {}),
  });
