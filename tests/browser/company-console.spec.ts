import { mkdir } from "node:fs/promises";
import path from "node:path";

import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

const SCREENSHOT_DIR = path.resolve("tests/browser/artifacts");

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

test("company console exposes position-owned recruiting operations", async ({
  page,
  request,
}) => {
  const browserErrors: string[] = [];
  const failedResponses: string[] = [];
  const position = await createRecruitingPosition(request);
  await issueInvitations(request, position.positionId, [
    {
      displayName: "브라우저 지원자",
      email: `browser-applicant-${position.suffix}@example.com`,
    },
  ]);

  page.on("console", (message) => {
    if (message.type() === "error") browserErrors.push(message.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      failedResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  const currentUser = page.waitForResponse(
    (response) =>
      response.url().endsWith("/v1/me") &&
      response.request().method() === "GET",
  );
  const positions = page.waitForResponse(
    (response) =>
      response.url().includes("/v1/positions?limit=100") &&
      response.request().method() === "GET",
  );
  const documentResponse = await page.goto("/company");

  expect(documentResponse?.status()).toBe(200);
  expect((await currentUser).status()).toBe(200);
  expect((await positions).status()).toBe(200);
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(245, 246, 248)",
  );
  await expect(
    page.getByRole("heading", { name: "채용 운영 대시보드" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "채용 관리", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "AI 면접관" })).toHaveCount(0);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-dashboard-desktop.png"),
    fullPage: true,
  });

  await page.getByRole("link", { name: "채용 포지션" }).click();
  await expect(page).toHaveURL(/\/positions$/);
  await page.getByRole("link", { name: `${position.title} 운영 보기` }).click();
  await expect(page).toHaveURL(
    new RegExp(`/positions/${position.positionId}$`),
  );
  await expect(
    page.getByRole("heading", { name: position.title }),
  ).toBeVisible();
  await expect(
    page.getByRole("tablist", { name: "포지션 운영 메뉴" }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "대시보드" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await expect(page.getByRole("tab", { name: "지원자 목록" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("heading", { name: "지원자 목록" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "지원자 초대 관리" }),
  ).toBeVisible();
  await expect(page.getByText("브라우저 지원자")).toBeVisible();
  await expect(
    page.getByText(`browser-applicant-${position.suffix}@example.com`),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "브라우저 지원자 상세 보기" }),
  ).toHaveAttribute(
    "href",
    new RegExp(`^/positions/${position.positionId}/applicants/[0-9a-f-]+$`),
  );
  await page.getByRole("button", { name: "초대 패널 접기" }).click();
  await expect(
    page.getByRole("button", { name: "초대 패널 펼치기" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "초대 패널 펼치기" }).click();
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-position-applicants.png"),
    fullPage: true,
  });

  expect(browserErrors).toEqual([]);
  expect(failedResponses).toEqual([]);
});

test("position settings can be edited and a draft can be confirmed", async ({
  page,
  request,
}) => {
  const position = await createRecruitingPosition(request);
  await page.goto(`/positions/${position.positionId}`);

  await expect(
    page.getByRole("heading", { name: position.title }),
  ).toBeVisible();
  await expect(
    page.locator(".position-workspace__title-line .status-badge"),
  ).toHaveText("초안");

  await page.getByRole("tab", { name: "포지션 정보" }).click();
  await expect(
    page.getByRole("heading", { name: "현재 적용 중인 면접 기준" }),
  ).toBeVisible();
  await expect(page.getByText(/버전/)).toHaveCount(0);

  await page.getByRole("button", { name: "간편 수정" }).click();
  await expect(
    page.getByRole("dialog", { name: "포지션 간편 수정" }),
  ).toBeVisible();
  await expect(page.getByLabel("포지션명")).toHaveValue(position.title);

  const revisedTitle = `시니어 플랫폼 ${position.suffix}`;
  await page.getByLabel("포지션명").fill(revisedTitle);
  await page.getByLabel("채용 인원").fill("4");
  const saved = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/v1/positions/${position.positionId}`) &&
      response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "변경 저장" }).click();
  expect((await saved).status()).toBe(200);
  await expect(page.getByRole("heading", { name: revisedTitle })).toBeVisible();

  const activated = page.waitForResponse(
    (response) =>
      response.url().endsWith(`/v1/positions/${position.positionId}`) &&
      response.request().method() === "PATCH",
  );
  await page.getByRole("button", { name: "간편 수정" }).click();
  await page.getByRole("button", { name: "채용 확정" }).click();
  expect((await activated).status()).toBe(200);
  await expect(
    page.locator(".position-workspace__title-line .status-badge"),
  ).toHaveText("운영 중");
  await page.getByRole("button", { name: "간편 수정" }).click();
  await expect(page.getByRole("button", { name: "채용 마감" })).toBeVisible();
  await page.getByRole("button", { name: "포지션 간편 수정 닫기" }).click();

  // Criterion editing is the other modal on this tab. It publishes a new immutable
  // criterion version, and the reason it is worth driving in a real browser is that the
  // recruiter must never see that: the workspace shows only what is currently applied.
  await page.getByRole("button", { name: "면접 기준 수정" }).click();
  const criteriaDialog = page.getByRole("dialog", { name: "면접 기준 수정" });
  await expect(criteriaDialog).toBeVisible();
  await expect(criteriaDialog.getByLabel("평가기준 이름 1")).toHaveValue(
    "문제 해결",
  );
  await criteriaDialog.getByLabel("평가기준 이름 1").fill("장애 대응 판단");
  const republished = page.waitForResponse(
    (response) =>
      response
        .url()
        .includes(
          `/v1/positions/${position.positionId}/competency-model-versions`,
        ) && response.request().method() === "POST",
  );
  await criteriaDialog.getByRole("button", { name: "변경 저장" }).click();
  expect((await republished).status()).toBe(201);
  await expect(criteriaDialog).toBeHidden();
  await expect(page.getByText("장애 대응 판단")).toBeVisible();
  await expect(page.getByText(/버전/)).toHaveCount(0);

  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-position-settings.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole("button", { name: "간편 수정" }).click();
  await expect(page.getByLabel("포지션명")).toHaveValue(revisedTitle);
  await expectNoHorizontalOverflow(page);
});

test("recruiter publishes criterion-grounded hiring settings without interviewer controls", async ({
  page,
}) => {
  const suffix = crypto.randomUUID().slice(0, 6);
  await page.goto("/hiring");
  await expect(page.getByText("AI 면접관")).toHaveCount(0);
  await page.getByLabel("포지션명").fill(`플랫폼 엔지니어 ${suffix}`);
  await page.getByRole("button", { name: /인프라·보안/ }).click();
  await page.getByLabel("채용 인원").fill("3");
  await page.getByLabel("모집 시작일").fill("2026-09-01");
  await page.getByLabel("모집 종료일").fill("2026-10-15");
  await page
    .getByLabel("포지션 설명")
    .fill("ECS 기반 서비스를 운영하고 장애 원인을 분석해 복구합니다.");
  await page.getByRole("button", { name: "포지션 만들기" }).click();

  await expect(
    page.getByRole("heading", { name: "면접 기준 설정" }),
  ).toBeVisible();
  await page
    .getByLabel("요구사항 1", { exact: true })
    .fill("ECS 운영 장애 대응 경험");
  await page.getByLabel("평가기준 이름 1").fill("운영 문제 해결");
  await page
    .getByLabel("설명 1")
    .fill("운영 장애의 원인을 분석하고 복구하는 역량");
  await expect(page.getByText("권장 기본값 적용됨")).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-criteria-editor-desktop.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "평가기준 게시" }).click();

  await expect(
    page.getByRole("heading", { name: "채용 기준 게시 완료" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "포지션 운영으로 이동" }),
  ).toBeVisible();
  await expect(page.getByText("지원자 이메일")).toHaveCount(0);
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
  });
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-criteria-published.png"),
    fullPage: true,
  });
});

test("position applicants can be invited in bulk without another setup layer", async ({
  page,
  request,
}) => {
  const position = await createRecruitingPosition(request);
  await page.goto(`/positions/${position.positionId}`);
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await expect(
    page.getByRole("heading", { name: "지원자 초대 관리" }),
  ).toBeVisible();

  await page.getByLabel("CSV 또는 JSON 가져오기").setInputFiles({
    name: "applicants.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      [
        "이름,이메일",
        "배치일,batch.one@example.com",
        "배치이,batch.two@example.com",
        "배치중복,BATCH.ONE@example.com",
        "확인필요,wrong-address",
      ].join("\n"),
    ),
  });
  await expect(page.getByText("발송 가능 2명")).toBeVisible();
  await expect(page.getByText("확인 필요 1명")).toBeVisible();
  await expect(page.getByText("중복 제외 1명")).toBeVisible();
  await expect(page.getByText("입력 명단 내 중복")).toBeVisible();
  await expect(page.getByText("이메일 형식을 확인하세요.")).toBeVisible();

  const issued = page.waitForResponse(
    (response) =>
      response
        .url()
        .includes(`/positions/${position.positionId}/invitations`) &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "2명에게 초대 보내기" }).click();
  expect((await issued).status()).toBe(202);

  await expect(page.getByText("2명의 초대를 발송했습니다.")).toBeVisible();
  await expect(page.getByText("배치일")).toBeVisible();
  await expect(page.getByText("batch.one@example.com")).toBeVisible();
  await expect(page.getByText("배치이")).toBeVisible();
  await expect(page.getByText("초대 발송").first()).toBeVisible();
  await expect
    .poll(async () => {
      const response = await request.get(
        "http://127.0.0.1:8025/api/v1/messages",
      );
      const body = (await response.json()) as {
        messages: Array<{ To: Array<{ Address: string }> }>;
      };
      const recipients = body.messages.flatMap((message) =>
        message.To.map((recipient) => recipient.Address),
      );
      return ["batch.one@example.com", "batch.two@example.com"].filter(
        (email) => recipients.includes(email),
      ).length;
    })
    .toBe(2);
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-position-invitations.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await expect(
    page.getByRole("heading", { name: "지원자 목록" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("local demo position shows a populated applicant roster", async ({
  page,
}) => {
  await page.goto("/positions");
  await page
    .getByRole("link", {
      name: "로컬 데모 백엔드 엔지니어 운영 보기",
    })
    .click();

  await expect(
    page.getByRole("heading", { name: "로컬 데모 백엔드 엔지니어" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "지원자 통계" }).click();
  await expect(page.getByLabel("전체 지원자 5명")).toBeVisible();
  await expect(page.getByLabel("진행 중인 지원자 2명")).toBeVisible();
  await expect(page.getByLabel("검토 대기 지원자 1명")).toBeVisible();
  await expect(page.getByLabel("완료된 지원자 1명")).toBeVisible();
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await expect(page.getByText("김하늘")).toBeVisible();
  await expect(page.getByText("윤지후")).toBeVisible();
  await expect(page.getByText("강민재")).toBeVisible();
  await expect(page.getByText("면접 준비", { exact: true })).toBeVisible();
  await expect(
    page.locator(".invitation-status").getByText("검토 완료", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("면접 완료", { exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-demo-applicant-roster.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(page.getByText("김하늘")).toBeVisible();
  await expectNoHorizontalOverflow(page);
});

test("position dashboard summarises applicants in aligned rows and columns", async ({
  page,
}) => {
  await page.goto("/positions");
  await page
    .getByRole("link", {
      name: "로컬 데모 백엔드 엔지니어 운영 보기",
    })
    .click();

  await expect(page.getByRole("tab", { name: "대시보드" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("heading", { name: "지원자 운영 현황" }),
  ).toBeVisible();
  await expect(page.getByLabel("전체 지원자 5명")).toBeVisible();
  await expect(page.getByLabel("진행 중 2명")).toBeVisible();
  await expect(page.getByLabel("검토 대기 1명")).toBeVisible();
  await expect(page.getByLabel("검토 완료 1명")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "최근 지원자" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "초대 현황" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "단계 분포" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "면접 기준 요약" }),
  ).toBeVisible();

  // The metrics row must lay out horizontally and the body must split into columns.
  const metricTops = await page
    .locator(".position-dashboard__metrics > article")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().top),
    );
  expect(metricTops.length).toBeGreaterThan(1);
  expect(new Set(metricTops).size).toBe(1);

  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-position-dashboard-desktop.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "지원자 운영 현황" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-position-dashboard-mobile.png"),
    fullPage: true,
  });
});

/**
 * The one path a reviewer actually walks: find the reviewable applicant, press 검토 시작,
 * and read why each question was asked. Everything here is served by the running stack, so
 * it covers the wiring the unit tests cannot see -- the timeline endpoint had shipped with
 * ``question_rationale: null`` for every session because the composed application built its
 * reporting router without the rationale provider, and the seed wrote its question
 * transcript segments against a fabricated turn id that no rationale could join.
 */
test("the seeded review screen shows what the applicant submitted behind each question", async ({
  page,
}) => {
  await page.goto("/positions");
  await page
    .getByRole("link", {
      name: "로컬 데모 백엔드 엔지니어 운영 보기",
    })
    .click();
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await page.getByRole("link", { name: /강민재/ }).click();

  await expect(page.getByRole("heading", { name: "강민재" })).toBeVisible();
  await page.getByRole("link", { name: "검토 시작" }).click();
  await expect(page).toHaveURL(/\/review\//);
  await expect(
    page.getByRole("heading", { name: "면접 타임라인" }),
  ).toBeVisible();

  // Three seeded questions, each carrying its own rationale disclosure.
  const rationales = page.locator(".question-rationale");
  await expect(rationales).toHaveCount(3);

  const first = rationales.first();
  await first.locator("summary").click();
  await expect(
    first.getByText("지원자 답변 Evidence가 아닌 질문 생성 참고 자료입니다."),
  ).toBeVisible();
  await expect(first.getByText("세부 내용 부족")).toBeVisible();
  // The excerpt is the applicant's own submitted line, not an answer and not a paraphrase.
  await expect(
    first.getByText(
      "결제 시스템 백엔드를 담당하며 일 300만 건 트래픽 증가에 대응했습니다.",
    ),
  ).toBeVisible();

  // The follow-up cites two pieces of material, one of them a file and symbol the
  // reviewer can locate in the submission.
  const second = rationales.nth(1);
  await second.locator("summary").click();
  await expect(second.getByText("본인 기여 확인")).toBeVisible();
  await expect(second.locator(".question-source-list > li")).toHaveCount(2);
  await expect(
    second.getByText("app/db/session.py", { exact: false }),
  ).toBeVisible();

  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-review-question-rationale.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const mobileRationales = page.locator(".question-rationale");
  await expect(mobileRationales).toHaveCount(3);
  // Scoped to the one disclosure being opened: the resume line is cited by two questions,
  // so a page-wide match would hit the still-collapsed second one as well.
  const mobileFirst = mobileRationales.first();
  await mobileFirst.locator("summary").click();
  await expect(
    mobileFirst.getByText(
      "결제 시스템 백엔드를 담당하며 일 300만 건 트래픽 증가에 대응했습니다.",
    ),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(
      SCREENSHOT_DIR,
      "company-review-question-rationale-mobile.png",
    ),
    fullPage: true,
  });
});

/**
 * The reviewer's video has to actually play. Three defects made it impossible while every
 * suite stayed green: the playback locator returned a hardcoded `https://media.local/...`
 * that resolves nowhere, the media worker wrote a recording asset naming an HLS manifest
 * nothing had produced, and the local seed marked that asset `ready` without ever
 * uploading bytes. Each layer passed its own tests -- and `head-object` on the key the
 * console put in `<video src>` returned 404.
 *
 * Nothing is mocked here. The URL is signed by the running API, fetched from the running
 * bucket, and decoded by the browser's own demuxer: `readyState > 0` and a non-zero
 * `videoWidth` are only reachable if real WebM bytes arrived over that URL.
 */
test("the seeded review screen plays the recording it cites", async ({
  page,
}) => {
  await page.goto("/positions");
  await page
    .getByRole("link", { name: "로컬 데모 백엔드 엔지니어 운영 보기" })
    .click();
  await page.getByRole("tab", { name: "지원자 목록" }).click();
  await page.getByRole("link", { name: /강민재/ }).click();
  await page.getByRole("link", { name: "검토 시작" }).click();
  await expect(page).toHaveURL(/\/review\//);

  // A `ready` badge beside a placeholder is exactly the state that shipped, so the badge
  // alone proves nothing -- the element below has to be a `<video>`, not the fallback.
  await expect(page.locator(".media-badge--ready")).toBeVisible();
  const video = page.locator(".timeline-media video");
  await expect(video).toHaveCount(1);

  const src = await video.getAttribute("src");
  expect(src).toBeTruthy();
  // Signed, and pointing at the assembled recording rather than at a placeholder host.
  expect(src).toContain("/recording/recording.webm");
  expect(src).toMatch(/Signature=|X-Amz-Signature=/);

  // The same URL the browser was handed, fetched independently: a 404 here is the original
  // defect, and it is invisible from the DOM because `<video>` fails silently.
  const response = await page.request.get(src!);
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toBe("video/webm");
  const body = await response.body();
  expect(body.length).toBeGreaterThan(1024);
  // EBML magic. A text or truncated placeholder of the right length fails this.
  expect([...body.subarray(0, 4)]).toEqual([0x1a, 0x45, 0xdf, 0xa3]);

  // And the browser's own demuxer agrees it is playable. `preload="metadata"` is enough to
  // reach HAVE_METADATA; a URL that 404s or serves the wrong container stays at 0.
  const metadata = await video.evaluate(async (element) => {
    const media = element as HTMLVideoElement;
    if (media.readyState === 0) {
      await new Promise<void>((resolve, reject) => {
        media.addEventListener("loadedmetadata", () => resolve(), {
          once: true,
        });
        media.addEventListener(
          "error",
          () => reject(new Error("video failed to load")),
          { once: true },
        );
        setTimeout(() => reject(new Error("video metadata timed out")), 15_000);
      });
    }
    return {
      readyState: media.readyState,
      duration: media.duration,
      videoWidth: media.videoWidth,
    };
  });
  expect(metadata.readyState).toBeGreaterThan(0);
  expect(metadata.videoWidth).toBeGreaterThan(0);
  // The seeded timeline's last citation ends at 160s, so a shorter recording cannot show
  // the evidence the report points at.
  expect(metadata.duration).toBeGreaterThanOrEqual(160);

  // Seeking to a cited range is what the reviewer does from the report, and a container
  // the browser cannot seek leaves them on the first frame.
  await video.evaluate(async (element) => {
    const media = element as HTMLVideoElement;
    media.currentTime = 120;
    await new Promise<void>((resolve) => {
      media.addEventListener("seeked", () => resolve(), { once: true });
      setTimeout(() => resolve(), 10_000);
    });
  });
  expect(
    await video.evaluate(
      (element) => (element as HTMLVideoElement).currentTime,
    ),
  ).toBeGreaterThan(0);

  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-review-video-playback.png"),
    fullPage: true,
  });
});

test("applicant management uses a readable cross-position operations layout", async ({
  page,
}) => {
  await page.goto("/applicants");

  await expect(
    page.getByRole("heading", { name: "지원자 관리" }),
  ).toBeVisible();
  await expect(page.getByLabel(/전체 지원자 \d+명/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "지원자 목록" }),
  ).toBeVisible();
  await page.getByLabel("지원자 검색").fill("로컬 데모");
  await expect(
    page.getByText("로컬 데모 백엔드 엔지니어").first(),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-applicant-management.png"),
    fullPage: true,
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "지원자 관리" }),
  ).toBeVisible();
  await page.getByLabel("지원자 검색").fill("로컬 데모");
  await expect(
    page.getByText("로컬 데모 백엔드 엔지니어").first(),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-applicant-management-mobile.png"),
    fullPage: true,
  });
});

test("applicant detail uses a tabbed comprehensive report layout", async ({
  page,
  request,
}) => {
  const position = await createRecruitingPosition(request);
  const [invitation] = await issueInvitations(request, position.positionId, [
    {
      displayName: "리포트 지원자",
      email: `report-applicant-${position.suffix}@example.com`,
    },
  ]);
  const detailPath = `/positions/${position.positionId}/applicants/${invitation.invitation_id}`;

  await page.goto(detailPath);
  await expect(
    page.getByRole("heading", { name: "리포트 지원자" }),
  ).toBeVisible();
  await expect(
    page.getByRole("tablist", { name: "지원자 리포트 메뉴" }),
  ).toBeVisible();
  await expect(page.getByLabel("현재 채용 단계 4단계 중 1단계")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "지원 진행 요약" }),
  ).toBeVisible();

  await page.getByRole("tab", { name: "제출 자료" }).click();
  await expect(
    page.getByRole("heading", { name: "제출 자료 처리 현황" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "제출 자료" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "면접 기록" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await page.getByRole("tab", { name: "면접 기록" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "분석 리포트" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    page.getByRole("heading", { name: "면접 분석 리포트" }),
  ).toBeVisible();

  await page.getByRole("tab", { name: "종합 개요" }).click();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-applicant-report.png"),
    fullPage: true,
  });

  await page.route(
    `**/v1/positions/${position.positionId}/invitations?limit=100`,
    async (route) => {
      const response = await route.fetch();
      const body = (await response.json()) as {
        items: Array<Record<string, unknown>>;
      };
      await route.fulfill({
        response,
        json: {
          ...body,
          items: body.items.map((item) =>
            item.invitation_id === invitation.invitation_id
              ? {
                  ...item,
                  status: "completed",
                  analysis_status: "ready",
                  interview_status: "completed",
                  report_status: "ready",
                  interview_session_id: "browser-review-session",
                }
              : item,
          ),
        },
      });
    },
  );
  await page.reload();
  await expect(page.getByLabel("현재 채용 단계 4단계 중 4단계")).toBeVisible();
  await page.getByRole("tab", { name: "분석 리포트" }).click();
  await expect(
    page.getByRole("link", { name: "전체 분석 리포트 열기" }),
  ).toHaveAttribute(
    "href",
    `/review/browser-review-session?invitationId=${invitation.invitation_id}`,
  );

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await expect(
    page.getByRole("tablist", { name: "지원자 리포트 메뉴" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-applicant-report-mobile.png"),
    fullPage: true,
  });
});

test("company recruiter workspace remains usable on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/company");

  await expect(
    page.getByRole("heading", { name: "채용 운영 대시보드" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-dashboard-mobile.png"),
    fullPage: true,
  });

  await page.getByRole("button", { name: "탐색 열기" }).click();
  await expect(page.getByRole("link", { name: "AI 면접관" })).toHaveCount(0);
  await page.getByRole("link", { name: "채용 관리", exact: true }).click();
  await expect(page).toHaveURL(/\/hiring$/);
  await expect(page.locator(".company-sidebar")).not.toHaveClass(/is-open/);
  await page.waitForTimeout(200);
  await expect(
    page.getByRole("heading", { name: "포지션 만들기" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-hiring-mobile.png"),
    fullPage: true,
  });

  const suffix = crypto.randomUUID().slice(0, 6);
  await page.getByLabel("포지션명").fill(`모바일 플랫폼 ${suffix}`);
  await page.getByLabel("채용 인원").fill("1");
  await page.getByLabel("모집 시작일").fill("2026-09-01");
  await page.getByLabel("모집 종료일").fill("2026-10-15");
  await page
    .getByLabel("포지션 설명")
    .fill("ECS 서비스를 운영하고 장애 원인을 분석합니다.");
  await page.getByRole("button", { name: "포지션 만들기" }).click();
  await expect(
    page.getByRole("heading", { name: "면접 기준 설정" }),
  ).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: path.join(SCREENSHOT_DIR, "company-criteria-editor-mobile.png"),
    fullPage: true,
  });
});

/**
 * The report is meant to hand a reviewer an A4 document, and printing is the only thing
 * that exercises the @media print rules, the @page size and page fragmentation. jsdom
 * has no layout and no print media, so nothing else in the suite can see this.
 *
 * Four real defects lived here behind a green suite: the console sidebar and topbar
 * printed on every page, `overflow: hidden` on the panel clipped everything past the
 * first page break rather than paginating it, the sheet's three-row grid kept its footer
 * with the first fragment so it overprinted the last criterion, and the page-content
 * padding left the sheet inset with the console canvas printed around it.
 *
 * The clips are asserted as computed styles rather than by reading the PDF: Chrome
 * subsets its fonts, so the printed text is not extractable, and the page count only
 * shows that the document paginated at all.
 */
test("the report prints as a document rather than as a screenshot of the console", async ({
  page,
}) => {
  const sessionId = "browser-print-session";
  const report = printableReport();
  await page.route(
    `**/v1/interview-sessions/${sessionId}/report`,
    async (route) => route.fulfill({ json: report }),
  );
  await page.route(
    `**/v1/interview-sessions/${sessionId}/timeline`,
    async (route) =>
      route.fulfill({
        json: {
          entries: [],
          playback: { url: null, expires_at: null, status: "unavailable" },
        },
      }),
  );

  await page.goto(`/review/${sessionId}?invitationId=${crypto.randomUUID()}`);
  await expect(
    page.getByRole("heading", { name: "면접 리포트" }),
  ).toBeVisible();
  await page.getByRole("tab", { name: "기준별 평가" }).click();

  await expect(page.locator(".report-item .report-axis")).toHaveCount(20);

  await page.emulateMedia({ media: "print" });

  // Navigation and controls are not part of the document.
  for (const selector of [
    ".company-sidebar",
    ".company-topbar",
    ".skip-link",
    ".report-document__tabs",
    ".review-workspace__timeline",
    ".review-workspace__decision",
  ]) {
    await expect(page.locator(selector)).toBeHidden();
  }

  // A clipping container cannot paginate, so this must not be `hidden` when printing.
  await expect(page.locator(".report-panel")).toHaveCSS("overflow", "visible");
  // Neither can a grid container fragment: as a grid the sheet kept its footer row with
  // the first page and printed it over the body instead of after it.
  await expect(page.locator(".report-page")).toHaveCSS("display", "block");

  // The sheet is the paper. Left inset means the console canvas prints around it.
  const sheet = await page.locator(".report-page").boundingBox();
  expect(sheet?.x).toBe(0);

  const pdf = await page.pdf({
    path: path.join(SCREENSHOT_DIR, "company-report-print.pdf"),
    format: "A4",
    printBackground: true,
  });

  // Four criteria of five axes each outgrow one A4 sheet, so the document has to paginate.
  // This is a floor on the artifact, not a substitute for the two rules above: it catches
  // the sheet being squeezed onto one page, while each clip is caught by its own rule.
  expect(countPdfPages(pdf)).toBeGreaterThanOrEqual(2);
});

/** Page count straight from the PDF, so pagination is asserted on the real artifact. */
function countPdfPages(pdf: Buffer) {
  return pdf.toString("latin1").match(/\/Type\s*\/Page[^s]/g)?.length ?? 0;
}

test("stale hashed assets return 404 instead of the SPA document", async ({
  request,
}) => {
  const response = await request.get("/assets/stale-company-build.js");
  const body = await response.text();

  expect(response.status()).toBe(404);
  expect(body).not.toContain('<div id="root">');
  expect(body).not.toContain("InterviewEP");
});

/**
 * A report long enough to need a second printed page: four criteria, five axes each.
 *
 * Four is what the seeded local report holds and what was measured to run past one A4
 * sheet; two criteria fit on one page and would make the pagination assertion vacuous.
 * Built here rather than seeded so the test does not depend on an interview having been
 * run. The last criterion is unscored on every axis, which is the case the sheet is most
 * likely to render as a zero.
 */
function printableReport() {
  const axes = [
    { axis: "correctness", label: "정확성", score: 61 },
    { axis: "depth", label: "깊이", score: 53 },
    { axis: "fundamentals", label: "CS 기본기", score: 46 },
    { axis: "ownership", label: "본인 기여", score: 66 },
    { axis: "communication", label: "설명력", score: 71 },
  ];
  const item = (name: string, scored: boolean) => ({
    report_item_id: crypto.randomUUID(),
    criterion_id: crypto.randomUUID(),
    criterion_name: name,
    assessment_state: scored ? "confirmed" : "insufficient_evidence",
    observation: scored
      ? "답변 1건을 근거로 이 기준을 검토했습니다."
      : "면접에서 이 기준을 확인할 답변이 기록되지 않았습니다.",
    rationale: "인용한 답변 구간에서 확인한 내용입니다.",
    uncertainty: "",
    follow_up_question: "구체적인 사례를 한 가지 더 확인해 주세요.",
    evidence: [],
    axis_assessments: axes.map((axis) => ({
      axis: axis.axis,
      label: axis.label,
      score: scored ? axis.score : null,
      rationale: scored
        ? `답변에서 ${axis.label}에 해당하는 내용을 확인했습니다.`
        : "인용할 답변이 없어 이 축은 판단하지 않았습니다.",
      quoted_evidence_ids: [],
    })),
  });

  return {
    report_id: crypto.randomUUID(),
    report_version: 1,
    status: "ready",
    summary: "지원자의 답변에서 확인한 내용을 기준별로 정리했습니다.",
    items: [
      item("장애 대응 판단", true),
      item("데이터 모델링", true),
      item("협업과 코드 리뷰", true),
      item("대규모 트래픽 운영", false),
    ],
    overall_score: 59,
    unscored_criteria_count: 1,
    ai_original_immutable: true,
    human_reviews: [],
  };
}

async function createRecruitingPosition(request: APIRequestContext) {
  const suffix = crypto.randomUUID();
  const headers = {
    Authorization: "Bearer local-company-token",
    "Content-Type": "application/json",
  };
  const title = `브라우저 초대 테스트 ${suffix.slice(0, 6)}`;
  const position = await request.post("/v1/positions", {
    headers: {
      ...headers,
      "Idempotency-Key": `browser-position-${suffix}`,
    },
    data: {
      title,
      description:
        "대량 초대와 지원자 진행 상태를 검증하는 테스트 포지션입니다.",
      role_type: "개발",
      headcount: 2,
      recruitment_start_at: "2026-09-01",
      recruitment_end_at: "2026-10-15",
    },
  });
  expect(position.status()).toBe(201);
  const positionBody = (await position.json()) as { position_id: string };

  const criteria = await request.post(
    `/v1/positions/${positionBody.position_id}/competency-model-versions`,
    {
      headers: {
        ...headers,
        "Idempotency-Key": `browser-criteria-${suffix}`,
      },
      data: {
        job_requirements: [
          {
            requirement_type: "required",
            statement: "운영 문제 해결 경험",
            priority: 1,
            criterion_code: "PROBLEM_SOLVING",
          },
        ],
        criteria: [
          {
            code: "PROBLEM_SOLVING",
            name: "문제 해결",
            description: "근거와 대안을 설명하는 능력",
            weight: 1,
            verification_guide: {
              observable_dimensions: ["상황", "본인 행동", "결과"],
              strong_answer_signals: ["구체적인 대안과 결과를 설명함"],
              weak_answer_signals: ["근거 없이 결과만 설명함"],
              follow_up_directions: ["본인이 직접 수행한 행동"],
              max_follow_ups: 1,
              time_budget_seconds: 300,
            },
            abstain_guidance: "최종 답변 근거가 없으면 판단을 유보한다.",
            common_questions: ["대안을 비교한 과정을 설명해 주세요."],
            required: true,
          },
        ],
        prohibited_topics: ["가족", "외모"],
        interview_duration_minutes: 30,
      },
    },
  );
  expect(criteria.status()).toBe(201);
  const criteriaBody = (await criteria.json()) as {
    competency_model_version_id: string;
    row_version: number;
  };
  const publishedCriteria = await request.post(
    `/v1/competency-model-versions/${criteriaBody.competency_model_version_id}/publish`,
    {
      headers: {
        ...headers,
        "Idempotency-Key": `browser-criteria-publish-${suffix}`,
        "If-Match-Version": String(criteriaBody.row_version),
      },
    },
  );
  expect(publishedCriteria.status()).toBe(200);

  return {
    positionId: positionBody.position_id,
    title,
    suffix: suffix.slice(0, 8),
  };
}

async function issueInvitations(
  request: APIRequestContext,
  positionId: string,
  applicants: readonly { displayName: string; email: string }[],
) {
  const response = await request.post(
    `/v1/positions/${positionId}/invitations`,
    {
      headers: {
        Authorization: "Bearer local-company-token",
        "Content-Type": "application/json",
        "Idempotency-Key": `browser-invitations-${crypto.randomUUID()}`,
      },
      data: {
        applicants: applicants.map((applicant) => ({
          email: applicant.email,
          display_name: applicant.displayName,
        })),
        expires_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
      },
    },
  );
  expect(response.status()).toBe(202);
  const body = (await response.json()) as {
    invitations: Array<{
      invitation_id: string;
      applicant_email: string;
    }>;
  };
  return body.invitations;
}
