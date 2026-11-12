import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

const python = fileURLToPath(
  new URL(
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python",
    import.meta.url,
  ),
);
const service = fileURLToPath(
  new URL("../tests/e2e_server.py", import.meta.url),
);

export default defineConfig({
  testDir: "./e2e",
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:8765",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${python}" "${service}"`,
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
