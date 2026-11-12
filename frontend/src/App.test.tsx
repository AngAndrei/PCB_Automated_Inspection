import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";
import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("uses the installed first profile when quality-v1 is not available", async () => {
  const model = {
    model_id: "custom-v1",
    label: "Custom detector",
    profiles: [{ profile_id: "fast-v1" }],
    class_names: [],
  };
  const image = {
    image_id: "image1",
    original_name: "board.png",
    width: 200,
    height: 100,
    url: "/api/artifacts/image1",
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/images")) return new Response(JSON.stringify(image));
      if (url.endsWith("/inspections") && init?.method === "POST") {
        if (JSON.parse(String(init.body)).profile_id !== "fast-v1")
          return new Response(JSON.stringify({ detail: "Unknown profile" }), {
            status: 422,
          });
        return new Response(
          JSON.stringify({
            inspection_id: "j1",
            image_id: "image1",
            image,
            model,
            profile: { profile_id: "fast-v1" },
            status: "queued",
            result: null,
            error: null,
            reviews: [],
            attempt: 0,
          }),
        );
      }
      return new Response(
        JSON.stringify(
          url.endsWith("/health")
            ? { worker_ready: true, model_ready: true }
            : url.endsWith("/models")
              ? { items: [model], errors: [] }
              : { items: [], total: 0 },
        ),
      );
    }),
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Upload PCB image"), {
    target: {
      files: [new File(["fixture"], "board.png", { type: "image/png" })],
    },
  });
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Run inspection" }),
    ).toBeEnabled(),
  );
  fireEvent.click(screen.getByRole("button", { name: "Run inspection" }));
  await screen.findByText("Waiting for the worker");
});

it("keeps inspection disabled when no trained PCB model is installed", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      async (url: string) =>
        new Response(
          JSON.stringify(
            url.endsWith("/health")
              ? { worker_ready: true, model_ready: false }
              : url.endsWith("/models")
                ? { items: [], errors: [], classes: [] }
                : { items: [], total: 0 },
          ),
          { headers: { "Content-Type": "application/json" } },
        ),
    ),
  );
  render(<App />);
  await screen.findByText("No PCB model installed");
  expect(
    screen.getByRole("button", { name: /Run inspection/i }),
  ).toBeDisabled();
  expect(screen.queryByText("No defects detected")).not.toBeInTheDocument();
});

it("shows a rejected upload and never enables inference for it", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/images"))
        return new Response(
          JSON.stringify({ detail: "Invalid image content" }),
          { status: 422 },
        );
      return new Response(
        JSON.stringify(
          url.endsWith("/health")
            ? { worker_ready: true, model_ready: true }
            : url.endsWith("/models")
              ? {
                  items: [
                    {
                      model_id: "test-v1",
                      label: "Test detector",
                      profiles: [{ profile_id: "quality-v1" }],
                      class_names: [],
                    },
                  ],
                  errors: [],
                  classes: [],
                }
              : { items: [], total: 0 },
        ),
      );
    }),
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Upload PCB image"), {
    target: {
      files: [new File(["broken"], "broken.png", { type: "image/png" })],
    },
  });
  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Invalid image content",
    ),
  );
  expect(
    screen.getByRole("button", { name: /Run inspection/i }),
  ).toBeDisabled();
});
