import { defineConfig, devices } from '@playwright/test';

/**
 * Dedicated Playwright Test project for the executions domain's execution
 * engine (see backend/app/domains/executions/tasks.py). Each automated
 * execution writes a generated test-case script into ./tests/ and runs it
 * against this config via `npx playwright test <file> --reporter=json`
 * (the CLI --reporter flag overrides the `reporter` option below, so
 * `npx playwright test` run by hand for manual debugging still gets a
 * readable list reporter).
 *
 * Uses the SYSTEM-INSTALLED Chrome (channel: 'chrome') instead of a
 * downloaded Chromium build, so `npx playwright test` works in this sandbox
 * without needing `playwright install` to fetch large browser binaries -
 * the same trick this project's frontend E2E verification has relied on in
 * every prior sprint. If `channel: 'chrome'` doesn't resolve Chrome on a
 * given machine, point `launchOptions.executablePath` at the real install
 * path instead (e.g. `C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe`
 * on Windows).
 */
export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.BASE_URL,
    trace: 'off',
    screenshot: 'off',
    video: 'off',
    actionTimeout: 15_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        channel: 'chrome',
      },
    },
  ],
});
