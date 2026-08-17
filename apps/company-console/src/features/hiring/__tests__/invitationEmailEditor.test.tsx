import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { InvitationEmailEditor } from "../InvitationEmailEditor";
import type {
  InvitationEmailTemplateApi,
  InvitationEmailTemplateState,
} from "../invitationEmailTemplate";

const template: InvitationEmailTemplateState = {
  subject: "[{{회사명}}] {{포지션명}} 면접 안내",
  headline: "서류 전형 합격을 축하드립니다",
  intro: "{{지원자명}}님, 지원해주셔서 감사합니다.",
  guides: ["소요 시간 | 약 25분", "준비물 | 조용한 공간"],
  ctaLabel: "면접 시작하기",
  outro: "곧 만나뵙기를 기대합니다.",
  footer: "문의: hiring@example.com",
  brandColor: "#5966ce",
  useApplicantName: true,
  emphasizeDeadline: true,
  showSecurityNotice: true,
  logoUrl: null,
  isPositionOverride: false,
};

function buildApi(
  overrides: Partial<InvitationEmailTemplateApi> = {},
): InvitationEmailTemplateApi {
  return {
    getCompanyTemplate: vi.fn().mockResolvedValue(template),
    saveCompanyTemplate: vi.fn((next) =>
      Promise.resolve({ ...template, ...next }),
    ),
    resetCompanyTemplate: vi.fn().mockResolvedValue(template),
    getPositionTemplate: vi.fn().mockResolvedValue(template),
    savePositionTemplate: vi.fn((_positionId, next) =>
      Promise.resolve({ ...template, ...next, isPositionOverride: true }),
    ),
    resetPositionTemplate: vi.fn().mockResolvedValue(template),
    previewTemplate: vi.fn((next) =>
      Promise.resolve({
        subject: next.subject,
        htmlBody: `<p>${next.headline}</p>`,
      }),
    ),
    uploadLogo: vi.fn().mockResolvedValue({
      logoUrl: "https://console.example/v1/public/companies/company-1/logo",
      contentType: "image/png",
      byteSize: 64,
    }),
    deleteLogo: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  };
}

describe("InvitationEmailEditor", () => {
  it("previews edits through the server renderer and saves the whole template", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);

    const headline = (await screen.findByRole("textbox", {
      name: /헤드라인/,
    })) as HTMLInputElement;
    expect(headline.value).toBe("서류 전형 합격을 축하드립니다");
    expect(screen.getByRole("button", { name: "저장" })).toHaveProperty(
      "disabled",
      true,
    );

    fireEvent.change(headline, { target: { value: "최종 면접에 초대합니다" } });

    // The console never renders email HTML itself, so the preview proves the copy
    // the recruiter approves is the copy the renderer will send.
    await waitFor(() =>
      expect(api.previewTemplate).toHaveBeenCalledWith(
        expect.objectContaining({ headline: "최종 면접에 초대합니다" }),
      ),
    );
    expect(
      (screen.getByTitle("초대 메일 미리보기") as HTMLIFrameElement).srcdoc,
    ).toContain("최종 면접에 초대합니다");

    fireEvent.click(screen.getByRole("button", { name: "저장" }));

    await waitFor(() =>
      expect(api.saveCompanyTemplate).toHaveBeenCalledWith(
        expect.objectContaining({
          headline: "최종 면접에 초대합니다",
          guides: ["소요 시간 | 약 25분", "준비물 | 조용한 공간"],
        }),
      ),
    );
    expect(
      await screen.findByText("전사 기본 초대 메일을 저장했습니다."),
    ).toBeTruthy();
  });

  it("adds a custom brand colour and normalises it before saving", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);
    await screen.findByRole("textbox", { name: /헤드라인/ });

    fireEvent.change(
      screen.getByRole("textbox", { name: "브랜드 색상 직접 입력" }),
      { target: { value: "#0F766E" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "색상 추가" }));

    const swatch = screen.getByRole("button", { name: "브랜드 색상 #0f766e" });
    expect(swatch.getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(api.saveCompanyTemplate).toHaveBeenCalledWith(
        expect.objectContaining({ brandColor: "#0f766e" }),
      ),
    );
  });

  it("rejects a malformed colour without touching the draft", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);
    await screen.findByRole("textbox", { name: /헤드라인/ });

    fireEvent.change(
      screen.getByRole("textbox", { name: "브랜드 색상 직접 입력" }),
      { target: { value: "teal" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "색상 추가" }));

    expect(
      screen.getByText("색상은 #RRGGBB 형식으로 입력하세요."),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "저장" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("uploads a logo and shows the URL the server derived for it", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);
    await screen.findByRole("textbox", { name: /헤드라인/ });
    expect(screen.getByText("로고 없음")).toBeTruthy();

    const file = new File([new Uint8Array(64)], "logo.png", {
      type: "image/png",
    });
    fireEvent.change(screen.getByLabelText("기업 로고 파일"), {
      target: { files: [file] },
    });

    await waitFor(() => expect(api.uploadLogo).toHaveBeenCalledWith(file));
    const logo = (await screen.findByAltText(
      "등록된 기업 로고",
    )) as HTMLImageElement;
    expect(logo.src).toBe(
      "https://console.example/v1/public/companies/company-1/logo",
    );
  });

  it("refuses an oversized logo locally instead of uploading it", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);
    await screen.findByRole("textbox", { name: /헤드라인/ });

    const file = new File([new Uint8Array(512 * 1024 + 1)], "logo.png", {
      type: "image/png",
    });
    fireEvent.change(screen.getByLabelText("기업 로고 파일"), {
      target: { files: [file] },
    });

    expect(
      await screen.findByText("로고 파일은 512KB 이하여야 합니다."),
    ).toBeTruthy();
    expect(api.uploadLogo).not.toHaveBeenCalled();
  });

  it("scopes position edits and reverts to the company-wide copy", async () => {
    const api = buildApi();

    render(
      <InvitationEmailEditor
        api={api}
        scope={{
          kind: "position",
          positionId: "position-1",
          positionName: "백엔드 엔지니어",
        }}
      />,
    );

    await screen.findByRole("textbox", { name: /헤드라인/ });
    expect(api.getPositionTemplate).toHaveBeenCalledWith("position-1");
    expect(screen.getByText(/이 포지션은 전사 기본값을 따릅니다/)).toBeTruthy();

    fireEvent.change(screen.getByRole("textbox", { name: /버튼 텍스트/ }), {
      target: { value: "지금 응답하기" },
    });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() =>
      expect(api.savePositionTemplate).toHaveBeenCalledWith(
        "position-1",
        expect.objectContaining({ ctaLabel: "지금 응답하기" }),
      ),
    );
    expect(api.saveCompanyTemplate).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /전사 기본값 따르기/ }));
    await waitFor(() =>
      expect(api.resetPositionTemplate).toHaveBeenCalledWith("position-1"),
    );
    expect(
      await screen.findByText("전사 기본값을 다시 따르도록 되돌렸습니다."),
    ).toBeTruthy();
  });

  it("keeps the platform default copy on the server when reverting", async () => {
    const api = buildApi();

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);
    await screen.findByRole("textbox", { name: /헤드라인/ });

    fireEvent.click(
      screen.getByRole("button", { name: /기본 문구로 되돌리기/ }),
    );

    // The default wording lives only in the renderer; the console asks for it
    // rather than shipping a copy that would drift.
    await waitFor(() => expect(api.resetCompanyTemplate).toHaveBeenCalled());
    expect(
      await screen.findByText("플랫폼 기본 문구로 되돌렸습니다."),
    ).toBeTruthy();
  });

  it("reports a load failure instead of rendering an empty form", async () => {
    const api = buildApi({
      getCompanyTemplate: vi.fn().mockRejectedValue(new Error("boom")),
    });

    render(<InvitationEmailEditor api={api} scope={{ kind: "company" }} />);

    expect(
      await screen.findByText("초대 메일 템플릿을 불러오지 못했습니다."),
    ).toBeTruthy();
  });
});
