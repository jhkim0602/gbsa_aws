import { InvitationEmailEditor } from "./InvitationEmailEditor";
import type { InvitationEmailTemplateApi } from "./invitationEmailTemplate";

export function InvitationEmailSettings({
  api,
}: {
  api: InvitationEmailTemplateApi;
}) {
  return (
    <section className="invitation-email-settings">
      <header className="page-header">
        <div>
          <p className="page-eyebrow">Invitation email</p>
          <h1>초대 메일 템플릿</h1>
          <p>
            모든 포지션이 기본으로 사용하는 초대 메일입니다. 포지션별로 다르게
            보내려면 해당 포지션의 초대 발송 화면에서 수정하세요.
          </p>
        </div>
      </header>
      <div className="page-content">
        <div className="panel">
          <InvitationEmailEditor api={api} scope={{ kind: "company" }} />
        </div>
      </div>
    </section>
  );
}
