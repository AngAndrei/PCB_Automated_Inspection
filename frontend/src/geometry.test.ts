import { describe, it, expect } from "vitest";
import { ellipse, fitTransform, imagePoint, zoomAt } from "./geometry";

describe("image coordinates", () => {
  it("centers a non-square image without stretching", () => {
    expect(fitTransform(1000, 500, 800, 600)).toEqual({
      scale: 0.8,
      x: 0,
      y: 100,
    });
  });
  it("maps a pointer back to the original image after pan and zoom", () => {
    expect(imagePoint(140, 100, { scale: 2, x: 20, y: 40 })).toEqual([60, 30]);
  });
  it("zooms around the pointer without moving its image point", () => {
    const before = { scale: 1, x: 0, y: 0 };
    const after = zoomAt(before, 200, 100, 2);
    expect(imagePoint(200, 100, after)).toEqual([200, 100]);
    expect(after.scale).toBe(2);
  });
  it("uses the same ellipse geometry as exported PNG", () => {
    expect(ellipse([420, 180, 455, 205])).toEqual({
      cx: 437.5,
      cy: 192.5,
      rx: 17.5,
      ry: 12.5,
    });
  });
});
