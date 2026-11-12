export interface Transform {
  scale: number;
  x: number;
  y: number;
}
export type Box = [number, number, number, number];

export function ellipse([x1, y1, x2, y2]: Box) {
  return {
    cx: (x1 + x2) / 2,
    cy: (y1 + y2) / 2,
    rx: (x2 - x1) / 2,
    ry: (y2 - y1) / 2,
  };
}
export function fitTransform(
  width: number,
  height: number,
  availableWidth: number,
  availableHeight: number,
): Transform {
  const scale = Math.min(availableWidth / width, availableHeight / height);
  return {
    scale,
    x: (availableWidth - width * scale) / 2,
    y: (availableHeight - height * scale) / 2,
  };
}
export function imagePoint(
  x: number,
  y: number,
  t: Transform,
): [number, number] {
  return [(x - t.x) / t.scale, (y - t.y) / t.scale];
}
export function zoomAt(
  t: Transform,
  x: number,
  y: number,
  factor: number,
): Transform {
  const scale = Math.max(0.03, Math.min(24, t.scale * factor));
  const [ix, iy] = imagePoint(x, y, t);
  return { scale, x: x - ix * scale, y: y - iy * scale };
}
