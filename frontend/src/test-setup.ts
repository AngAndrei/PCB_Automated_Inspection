import "@testing-library/jest-dom/vitest";
import { vi, beforeEach } from "vitest";

// jsdom has no layout engine; image-coordinate math is tested independently.
beforeEach(() =>
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  ),
);
