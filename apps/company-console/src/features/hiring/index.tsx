import { FormEvent, useState } from "react";

export type HiringWorkspaceApi = {
  createPosition(input: {
    title: string;
    description: string;
  }): Promise<{ positionId: string }>;
  publishCriteria(
    positionId: string,
    name: string,
  ): Promise<{ versionId: string }>;
  createCampaign(
    positionId: string,
    versionId: string,
    name: string,
  ): Promise<{ campaignId: string }>;
  issueInvitation(campaignId: string, email: string): Promise<void>;
};

type Step = "position" | "criteria" | "campaign" | "invitation" | "complete";

export function HiringWorkspace({ api }: { api: HiringWorkspaceApi }) {
  const [step, setStep] = useState<Step>("position");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criterionName, setCriterionName] = useState("");
  const [campaignName, setCampaignName] = useState("");
  const [email, setEmail] = useState("");
  const [positionId, setPositionId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [campaignId, setCampaignId] = useState("");

  async function submitPosition(event: FormEvent) {
    event.preventDefault();
    const created = await api.createPosition({ title, description });
    setPositionId(created.positionId);
    setStep("criteria");
  }

  async function submitCriteria(event: FormEvent) {
    event.preventDefault();
    const published = await api.publishCriteria(positionId, criterionName);
    setVersionId(published.versionId);
    setStep("campaign");
  }

  async function submitCampaign(event: FormEvent) {
    event.preventDefault();
    const created = await api.createCampaign(
      positionId,
      versionId,
      campaignName,
    );
    setCampaignId(created.campaignId);
    setStep("invitation");
  }

  async function submitInvitation(event: FormEvent) {
    event.preventDefault();
    await api.issueInvitation(campaignId, email);
    setStep("complete");
  }

  return (
    <main>
      <header>
        <p>GBSA Interview Evidence</p>
        <h1>채용 캠페인</h1>
      </header>

      {step === "position" && (
        <form onSubmit={submitPosition}>
          <h2>포지션 만들기</h2>
          <label>
            포지션명
            <input
              required
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
          </label>
          <label>
            포지션 설명
            <textarea
              required
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </label>
          <button type="submit">포지션 만들기</button>
        </form>
      )}

      {step === "criteria" && (
        <form onSubmit={submitCriteria}>
          <h2>평가기준 작성</h2>
          <label>
            평가기준 이름
            <input
              required
              value={criterionName}
              onChange={(event) => setCriterionName(event.target.value)}
            />
          </label>
          <button type="submit">평가기준 게시</button>
        </form>
      )}

      {step === "campaign" && (
        <form onSubmit={submitCampaign}>
          <h2>캠페인 설정</h2>
          <label>
            캠페인 이름
            <input
              required
              value={campaignName}
              onChange={(event) => setCampaignName(event.target.value)}
            />
          </label>
          <button type="submit">캠페인 만들기</button>
        </form>
      )}

      {step === "invitation" && (
        <form onSubmit={submitInvitation}>
          <h2>지원자 초대</h2>
          <label>
            지원자 이메일
            <input
              required
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </label>
          <button type="submit">초대 보내기</button>
        </form>
      )}

      {step === "complete" && <p role="status">초대를 보냈습니다.</p>}
    </main>
  );
}
