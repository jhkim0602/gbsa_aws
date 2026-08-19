import {
  PAGE_CONTENT,
  PAGE_EYEBROW_IN_HEADER,
  PAGE_HEADER,
  PAGE_HEADER_TEXT,
  PAGE_HEADER_TITLE,
} from "../../app/styles/primitives";
import { InvitationEmailEditor } from "./InvitationEmailEditor";
import type { InvitationEmailTemplateApi } from "./invitationEmailTemplate";

export function InvitationEmailSettings({
  api,
}: {
  api: InvitationEmailTemplateApi;
}) {
  return (
    <section>
      <header className={PAGE_HEADER}>
        <div>
          {/* `.page-eyebrow` loses its colour, size and margin to `.page-header p`
              (0,1,1 beats 0,1,0), so this renders 14px/muted, not 9px/brand. */}
          <p className={PAGE_EYEBROW_IN_HEADER}>Invitation email</p>
          <h1 className={PAGE_HEADER_TITLE}>초대 메일 템플릿</h1>
          <p className={PAGE_HEADER_TEXT}>
            모든 포지션이 기본으로 사용하는 초대 메일입니다. 포지션별로 다르게
            보내려면 해당 포지션의 초대 발송 화면에서 수정하세요.
          </p>
        </div>
      </header>
      <div className={PAGE_CONTENT}>
        {/* `.invitation-email-settings .panel` overrides `.panel`: no padding, clipped. */}
        <div className="overflow-hidden rounded-xl border border-border bg-surface shadow-soft">
          <InvitationEmailEditor api={api} scope={{ kind: "company" }} />
        </div>
      </div>
    </section>
  );
}
