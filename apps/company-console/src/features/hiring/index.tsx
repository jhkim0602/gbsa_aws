import { FormEvent, useState } from "react";

export type HiringWorkspaceApi = {
  createPosition(input: {
    title: string;
    description: string;
  }): Promise<{ positionId: string }>;
  publishCriteria(
    positionId: string,
    input: CriteriaConfiguration,
  ): Promise<{ versionId: string }>;
  previewVoice(persona: CriteriaConfiguration["persona"]): void;
  createCampaign(
    positionId: string,
    versionId: string,
    name: string,
  ): Promise<{ campaignId: string }>;
  issueInvitation(campaignId: string, email: string): Promise<void>;
};

export type CriteriaConfiguration = Readonly<{
  criteria: ReadonlyArray<{
    code: string;
    name: string;
    description: string;
    weight: number;
    goodEvidence: string;
    weakEvidence: string;
    abstainGuidance: string;
    commonQuestions: string[];
    required: boolean;
  }>;
  prohibitedTopics: string[];
  interviewDurationMinutes: number;
  persona: {
    name: string;
    tone: string;
    voiceId: string;
  };
}>;

type Step = "position" | "criteria" | "campaign" | "invitation" | "complete";

export function HiringWorkspace({ api }: { api: HiringWorkspaceApi }) {
  const [step, setStep] = useState<Step>("position");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criterionName, setCriterionName] = useState("");
  const [criterionDescription, setCriterionDescription] = useState("");
  const [goodEvidence, setGoodEvidence] = useState("");
  const [weakEvidence, setWeakEvidence] = useState("");
  const [abstainGuidance, setAbstainGuidance] = useState("");
  const [commonQuestions, setCommonQuestions] = useState("");
  const [prohibitedTopics, setProhibitedTopics] = useState("");
  const [interviewDurationMinutes, setInterviewDurationMinutes] = useState(30);
  const [personaName, setPersonaName] = useState("GBSA AI 면접관");
  const [personaTone, setPersonaTone] = useState("차분하고 간결함");
  const [voiceId, setVoiceId] = useState("Seoyeon");
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
    const published = await api.publishCriteria(positionId, {
      criteria: [
        {
          code: "PROBLEM_SOLVING",
          name: criterionName,
          description: criterionDescription || criterionName,
          weight: 1,
          goodEvidence,
          weakEvidence,
          abstainGuidance,
          commonQuestions: splitLines(commonQuestions),
          required: true,
        },
      ],
      prohibitedTopics: splitCommaSeparated(prohibitedTopics),
      interviewDurationMinutes,
      persona: {
        name: personaName,
        tone: personaTone,
        voiceId,
      },
    });
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
          <label>
            평가기준 설명
            <textarea
              value={criterionDescription}
              onChange={(event) => setCriterionDescription(event.target.value)}
            />
          </label>
          <label>
            좋은 Evidence
            <textarea
              required
              value={goodEvidence}
              onChange={(event) => setGoodEvidence(event.target.value)}
            />
          </label>
          <label>
            약한 Evidence
            <textarea
              required
              value={weakEvidence}
              onChange={(event) => setWeakEvidence(event.target.value)}
            />
          </label>
          <label>
            판단 유보 기준
            <textarea
              required
              value={abstainGuidance}
              onChange={(event) => setAbstainGuidance(event.target.value)}
            />
          </label>
          <label>
            공통 질문
            <textarea
              required
              value={commonQuestions}
              onChange={(event) => setCommonQuestions(event.target.value)}
            />
          </label>
          <label>
            금지 주제
            <input
              required
              value={prohibitedTopics}
              onChange={(event) => setProhibitedTopics(event.target.value)}
            />
          </label>
          <label>
            면접 시간(분)
            <input
              required
              type="number"
              min={10}
              max={120}
              value={interviewDurationMinutes}
              onChange={(event) =>
                setInterviewDurationMinutes(Number(event.target.value))
              }
            />
          </label>
          <label>
            면접관 이름
            <input
              required
              value={personaName}
              onChange={(event) => setPersonaName(event.target.value)}
            />
          </label>
          <label>
            면접관 말투
            <input
              required
              value={personaTone}
              onChange={(event) => setPersonaTone(event.target.value)}
            />
          </label>
          <label>
            음성
            <select
              value={voiceId}
              onChange={(event) => setVoiceId(event.target.value)}
            >
              <option value="Seoyeon">서연</option>
              <option value="Jihye">지혜</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() =>
              api.previewVoice({
                name: personaName,
                tone: personaTone,
                voiceId,
              })
            }
          >
            음성 미리듣기
          </button>
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

function splitLines(value: string): string[] {
  return value
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function splitCommaSeparated(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}
