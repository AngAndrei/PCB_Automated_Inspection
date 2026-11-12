import { test, expect } from "@playwright/test";

test.afterAll(async ({ request }) => {
  await request.post("/__test__/shutdown");
});

test("upload, inspect, select region, review, export and reopen history", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByText("Worker online")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run inspection" }),
  ).toBeDisabled();
  // Generated in the browser: a test-only RGB PNG with no external dataset dependency.
  const base64 = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 200;
    canvas.height = 100;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, 200, 100);
    ctx.strokeStyle = "#327f61";
    ctx.lineWidth = 4;
    ctx.strokeRect(20, 20, 150, 60);
    return canvas.toDataURL("image/png").split(",")[1];
  });
  await page.getByLabel("Upload PCB image").setInputFiles({
    name: "fixture-board.png",
    mimeType: "image/png",
    buffer: Buffer.from(base64, "base64"),
  });
  await expect(
    page.getByRole("button", { name: "Run inspection" }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Run inspection" }).click();
  await expect(
    page.getByText("Defects detected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Approximate defect areas")).toBeVisible();
  await page.getByRole("button", { name: /Open circuit.*94%/ }).click();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Visible trace break");
  await page.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  await page.getByLabel("Overlay opacity").fill("60");
  await page.getByLabel("Zoom in", { exact: true }).click();
  await page.getByLabel("Fit image", { exact: true }).click();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "JSON", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.json$/);
  // History can be a cached snapshot; reopening must load the current saved review.
  const staleHistory = await (
    await page.request.get("/api/inspections")
  ).json();
  for (const item of staleHistory.items) item.reviews = [];
  await page.route(/\/api\/inspections(?:\?.*)?$/, async (route) => {
    if (route.request().method() === "GET")
      await route.fulfill({ json: staleHistory });
    else await route.continue();
  });
  await page.getByRole("button", { name: /History/ }).click();
  await page
    .getByRole("button", { name: /fixture-board.png/ })
    .first()
    .click();
  await expect(page.getByText("Confirmed", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/inspection-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByText("Approximate defect areas")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/inspection-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
