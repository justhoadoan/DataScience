import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:8000",
    ...devices["Desktop Chrome"],
    launchOptions: process.env.CHROME_PATH
      ? { executablePath: process.env.CHROME_PATH }
      : {},
  },
  webServer: {
    command: `${process.env.PYTHON_BIN || "python"} -m hanoi_rentals.cli --root .. serve --port 8000`,
    url: "http://127.0.0.1:8000/api/health",
    reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
