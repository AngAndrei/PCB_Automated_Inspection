import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function transport(deferred: "inspect" | "review") {
  let release!: (value: Response) => void;
  const pending = new Promise<Response>((resolve) => {
    release = resolve;
  });
  const model = {
    model_id: "m",
    label: "Detector",
    profiles: [{ profile_id: "quality-v1" }],
    class_names: [],
  };
  const image = (id: string) => ({
    image_id: id,
    original_name: `${id}.png`,
    width: 100,
    height: 100,
    url: `/api/artifacts/${id}`,
  });
  const record = (id: string, cls: number, name: string) => ({
    inspection_id: id,
    image_id: id,
    image: image(id),
    model,
    profile: { profile_id: "quality-v1" },
    status: "completed",
    created_at: "2026-11-12T09:00:00Z",
    attempt: 1,
    reviews: [],
    error: null,
    result: {
      decision: "defects_detected",
      defects: [
        {
          defect_id: "d1",
          class_id: cls,
          class_name: name,
          confidence: 0.94,
          bbox_xyxy: [10, 10, 30, 30],
          localization_kind: "bbox_region",
          mask_ref: null,
        },
      ],
      timings_ms: { total: 2 },
      warnings: [],
    },
  });
  const a = record("A", 0, "open_circuit"),
    b = record("B", 3, "spur");
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/health"))
        return Response.json({ worker_ready: true, model_ready: true });
      if (url.endsWith("/models"))
        return Response.json({ items: [model], errors: [] });
      if (url.endsWith("/images")) return Response.json(image("A"));
      if (init?.method === "POST" && url.endsWith("/reviews")) return pending;
      if (init?.method === "POST" && url.endsWith("/inspections"))
        return pending;
      if (url.endsWith("/inspections/A")) return Response.json(a);
      if (url.endsWith("/inspections/B")) return Response.json(b);
      return Response.json({ items: [a, b], total: 2 });
    }),
  );
  return {
    resolve: () =>
      release(
        Response.json(
          deferred === "inspect"
            ? { ...a, status: "queued", result: null }
            : {
                review_id: "r1",
                inspection_id: "A",
                defect_id: "d1",
                verdict: "confirmed",
                note: "A only",
                created_at: "2026-11-12T09:01:00Z",
              },
        ),
      ),
  };
}

async function openBoard(name: string) {
  fireEvent.click(screen.getByRole("button", { name: /History/ }));
  fireEvent.click(
    await screen.findByRole("button", { name: new RegExp(`${name}.png`) }),
  );
  await screen.findByLabelText(new RegExp(`Inspection image: ${name}.png`));
}

it("keeps board B selected when a pending inspection for A returns", async () => {
  const pending = transport("inspect");
  render(<App />);
  fireEvent.change(screen.getByLabelText("Upload PCB image"), {
    target: { files: [new File(["a"], "A.png", { type: "image/png" })] },
  });
  await screen.findByRole("button", { name: /Change board image/ });
  fireEvent.click(screen.getByRole("button", { name: "Run inspection" }));
  await openBoard("B");
  await act(async () => pending.resolve());
  expect(
    screen.getByRole("button", { name: /Spur.*Awaiting review/ }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText(/Inspection image: B.png/)).toBeInTheDocument();
});

it("does not append an A review to B when defect IDs repeat", async () => {
  const pending = transport("review");
  render(<App />);
  await screen.findByText("Worker online");
  await openBoard("A");
  fireEvent.click(
    screen.getByRole("button", { name: /Open circuit.*Awaiting review/ }),
  );
  fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
  await openBoard("B");
  await act(async () => pending.resolve());
  expect(
    screen.getByRole("button", { name: /Spur.*Awaiting review/ }),
  ).toBeInTheDocument();
  expect(
    screen.queryByText("Confirmed", { exact: true }),
  ).not.toBeInTheDocument();
});
