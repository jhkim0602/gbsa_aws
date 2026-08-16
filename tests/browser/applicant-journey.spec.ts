import { mkdir } from "node:fs/promises";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const SCREENSHOT_DIR = path.resolve("tests/browser/artifacts");

function observeBrowser(page: Page) {
  const browserErrors: string[] = [];
  const failedResponses: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  return { browserErrors, failedResponses };
}

async function expectNoHorizontalOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth,
  }));

  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);
}

test.beforeAll(async () => {
  await mkdir(SCREENSHOT_DIR, { recursive: true });
});

test("applicant portal renders the real journey routes without browser errors", async ({
  page,
}) => {
  const observed = observeBrowser(page);

  const accessResponse = await page.goto("/access/demo-token");
  expect(accessResponse?.status()).toBe(200);
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(245, 246, 248)",
  );
  await expect(page.getByRole("banner")).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "지원자 면접" }),
  ).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "면접 진행 단계" }),
  ).toBeVisible();
  await expect(page.getByLabel("초대 확인")).toHaveAttribute(
    "aria-current",
    "step",
  );
  await expect(page.getByRole("button", { name: "초대 확인" })).toHaveCSS(
    "background-color",
    "rgb(89, 102, 206)",
  );
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-access-desktop.png"),
    fullPage: true,
  });

  const submissionsResponse = await page.goto("/submissions");
  expect(submissionsResponse?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "지원 자료 제출" }),
  ).toBeVisible();
  await expect(page.getByLabel("자료 제출")).toHaveAttribute(
    "aria-current",
    "step",
  );
  await expect(page.getByLabel("PDF 자료")).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-submissions-desktop.png"),
    fullPage: true,
  });

  const interviewResponse = await page.goto("/interview");
  expect(interviewResponse?.status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "면접 환경 점검" }),
  ).toBeVisible();
  await expect(page.getByLabel("환경 점검")).toHaveAttribute(
    "aria-current",
    "step",
  );
  await expect(
    page.getByText("기술 문제는 면접 평가에 영향을 주지 않습니다."),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-equipment-desktop.png"),
    fullPage: true,
  });

  expect(observed.browserErrors).toEqual([]);
  expect(observed.failedResponses).toEqual([]);
});

test("applicant portal remains usable at a 390px mobile viewport", async ({
  page,
}) => {
  const observed = observeBrowser(page);
  await page.setViewportSize({ width: 390, height: 844 });

  await page.goto("/access/demo-token");
  await expect(
    page.getByRole("heading", { name: "지원자 면접" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-access-mobile.png"),
    fullPage: true,
  });

  await page.goto("/submissions");
  await expect(
    page.getByRole("heading", { name: "지원 자료 제출" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-submissions-mobile.png"),
    fullPage: true,
  });

  await page.goto("/interview");
  await expect(
    page.getByRole("heading", { name: "면접 환경 점검" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "applicant-equipment-mobile.png"),
    fullPage: true,
  });

  expect(observed.browserErrors).toEqual([]);
  expect(observed.failedResponses).toEqual([]);
});
