# Track 3 — 면접 현장 정합성 + 접근 경로

**목표:** 담당자가 설정한 것이 지원자 화면에 그대로 도달하게 만든다. 초대 링크가 실제로 작동하게 하고, 면접관 3인이 말하는 것처럼 움직이게 하고, 긴 면접의 컨텍스트를 관리한다.

**우선순위:** 이 트랙의 34–36(초대 URL/토큰)이 **전 프로젝트 최우선**이다. 초대 링크가 작동하지 않으면 다른 모든 기능에 도달할 수 없다.

**다른 트랙과의 겹침:** 아바타 립싱크만 Track 1의 `speech_marks` JSON 스키마에 의존한다. 나머지는 즉시 착수 가능.

---

## A. 초대 URL / 토큰 (최우선)

### A.1 결함 — 토큰이 유실된다

**발송하는 쪽** (`company_management/api/company_routes.py:690`):

```python
invitation_url=(f"{applicant_access_base_url}?token={issuance.token.raw_token}")
```

**읽는 쪽** (`apps/applicant-interview/src/app/routeAdapters.tsx:280`):

```tsx
const { token = "" } = useParams();
```

라우트 선언 (`apps/applicant-interview/src/app/featureRoutes.ts:29-30`):

```
{ path: "access",        Component: AccessRoute },
{ path: "access/:token", Component: AccessRoute },
```

`/access?token=abc`는 `path: "access"`에 매칭되고, `useParams().token`은 `""`다. **토큰이 화면에 도달하지 않는다.** `useSearchParams`로 토큰을 읽는 코드는 지원자 SPA에 존재하지 않는다. `ApplicantAccess`(`features/access/index.tsx:150`)는 `step="exchange"`로 시작해 빈 토큰으로 `api.exchangeToken("")`을 호출한다.

### A.2 쿼리 스트링을 고르지 않는다 — 경로로 고친다

두 가지 수정이 가능하다: (a) 프론트가 쿼리를 읽게 하거나, (b) 백엔드가 경로로 보내게 하거나. **(b)를 고른다.**

이유는 이 레포에 이미 기록된 사고다. `reporting/application/timeline_service.py:82-87`에 자유 텍스트 `query` 파라미터가 지원자의 답변 텍스트를 **ALB 액세스 로그로 S3에 기록한** 사건이 문서화돼 있고, 그래서 그 엔드포인트에는 지금 쿼리 파라미터가 없다. 쿼리 스트링에 들어간 값은 브라우저 히스토리, Referer 헤더, ALB 액세스 로그에 남는다. **초대 토큰은 그 자체가 인증 자격이다.**

`git_fetch.py:160-161`도 같은 원칙을 명시한다: GitHub 토큰은 "요청 헤더에만 놓이고 스냅샷·에러 코드·로그 라인에는 절대 놓이지 않는다."

**수정:**

```python
# company_routes.py:690
invitation_url=f"{applicant_access_base_url}/{issuance.token.raw_token}"
```

`_applicant_access_base_url`(`runtime/production.py:478-482`)이 이미 `"?" in value`를 거부하고 `rstrip("/")`를 하므로 경로 결합이 안전하다.

`routeAdapters.tsx:280`의 `useParams()`는 **그대로 둔다** — `access/:token` 라우트가 이미 있고 이제 실제로 매칭된다.

**추가로:** `path: "access"`(토큰 없음)로 들어온 경우 토큰 입력 화면을 유지한다. 메일을 잃은 지원자의 유일한 경로다.

### A.3 죽은 링크 기본값 제거

`company_routes.py:327`:

```python
applicant_access_base_url: str = "https://applicant.local/access"
```

`api/__init__.py:72`와 `:160`에도 같은 기본값이 있다. `runtime/production.py`는 `APPLICANT_ACCESS_BASE_URL`이 없으면 예외를 던지지만(`:481`), 라우터 팩토리를 직접 부르는 경로는 조용히 `applicant.local`로 발송한다. **기본값을 제거하고 필수 인자로 만든다.**

테스트 3곳(`test_lane_a_quickstart.py:42`, `test_invitation_delivery_failure.py:197/272`)이 이미 명시적으로 넘기고 있으므로 테스트 수정 불필요.

### A.4 토큰 교환은 이미 올바르다 — 건드리지 않는다

`company_management/domain/hiring.py:106-109`: `token_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")` + `expires_at` + `identity_verified_at`. 해시만 저장한다.

교환은 `POST /applicant/access/exchange`(`applicant_routes.py:125-136`)에서 **request body**로 받아 세션 쿠키로 바꾼다 — `invitation_token: str = Field(min_length=32, max_length=4096)`. 이 설계는 정확하다. body이므로 로그에 남지 않는다.

### A.5 검증

1. `POST /positions/{id}/invitations`로 초대를 발급하고 발송된 `invitation_url`이 `/access/{token}` 형태임을 확인.
2. 그 URL로 접속 → `useParams().token`이 채워짐 → `exchangeToken`이 성공 → 쿠키 발급 → `step="identity"`로 진행.
3. 통합 테스트: 발송 URL을 파싱해 그 경로로 exchange를 호출하는 end-to-end 케이스. **URL을 만드는 쪽과 읽는 쪽을 같은 테스트가 잇지 않으면 이 버그가 재발한다.**

---

## B. 면접 레벨이 지원자에게 도달하지 않는다

### B.1 결함

`routeAdapters.tsx:335`:

```tsx
const interviewerLevel = parseInterviewerLevel(search.get("level"));
```

`routeAdapters.tsx:268-273`:

```tsx
function parseInterviewerLevel(value: string | null): InterviewerLevel {
  if (value && value in INTERVIEWER_LEVELS) return value as InterviewerLevel;
  return "entry";
}
```

`routeAdapters.tsx:389`이 세션 생성 후 `new URLSearchParams({ level: interviewerLevel })`로 URL에 다시 넣는다.

**결과 두 가지:**
1. **레벨이 URL 쿼리에서 온다.** 서버가 알려주지 않는다. 담당자가 시니어로 설정해도 지원자는 신입 면접관 얼굴을 본다 (기본값 `"entry"`).
2. **지원자가 바꿀 수 있다.** `?level=senior`를 직접 붙이면 아바타가 바뀐다.

질문 자체는 서버가 정하므로(아래 B.2) 면접 내용은 조작되지 않는다. 하지만 **화면과 실제가 어긋난다.**

### B.2 서버 측은 정상이다 — 확인된 사실

레벨은 서버에서 끝까지 흐른다:

```
CompetencyModelVersion.interview_level  (criteria.py:113, default JUNIOR)
  → CriterionVersionSnapshot.interview_level  (company_service.py:83)
  → InterviewPlan.interview_level  (submission_interview.py:222)
  → live_handlers.py:444  interview_level=plan.interview_level
  → question_prompt.py  레벨별 프롬프트 템플릿 + max_question_length
  → InterviewPlan.follow_up_budget()  (interview_plan.py:81)
      → InterviewLevel.follow_up_budget(configured)  (shared/interview_level.py:30)
  → ReportGenerator.generate(interview_level=...)  (runtime/worker.py:249)
```

`shared/interview_level.py`의 정책: ENTRY는 꼬리질문 1개로 상한(첫 직장 지원자를 한 기준으로 3단계까지 파지 않는다), SENIOR는 `min(bounded+1, 3)`, 설정이 0이면 어떤 레벨도 추가하지 않는다.

**즉 서버는 옳고, 프론트만 서버에게 묻지 않고 있다.**

### B.3 수정

**세션 응답에 레벨을 실어 보낸다.** `InterviewSessionView`(`interview_engine/api/applicant_routes.py:63-70`)에 필드 추가:

```python
class InterviewSessionView(BaseModel):
    interview_session_id: UUID
    state: str
    session_sequence: int
    websocket_path: str
    protocol_version: str
    interview_level: str      # 신규
```

`create_interview_session`(`:201`)에서 `service.create_session(...)`이 반환하는 세션에 레벨이 없다면, `InterviewPlanProvider`(`interview_plan.py:114`)로 plan을 얻어 `plan.interview_level.value`를 넣는다 — 세션 생성 시점에 plan은 이미 해석 가능하다.

**프론트:**
- `parseInterviewerLevel(search.get("level"))` 제거.
- `session.interview_level`을 상태에 담아 `InterviewRoom`에 넘긴다.
- `routeAdapters.tsx:389`에서 `level`을 URL에 다시 쓰지 않는다. `strategyId`만 남긴다.
- `Avatar.tsx:34`의 `level = "entry"` 기본값을 제거하고 **필수 prop**으로 만든다. 기본값이 있으면 배선을 잊어도 조용히 신입 얼굴이 나온다.
- `routeAdapters.tsx:342`의 dev 프리뷰(`?preview=room`)는 URL 레벨을 유지해도 된다 — `import.meta.env.DEV` 가드 안이다.

`packages/contracts/openapi/paths/interview/`의 스키마와 `generated/typescript/openapi.d.ts`를 재생성한다 (`npm run contracts:generate`).

---

## C. 면접관 3인을 실제로 움직인다

### C.1 에셋은 이미 완비돼 있다

`apps/applicant-interview/public/interviewers/` — 18장:

```
{entry|junior|senior}_eyes_{open|closed}_mouth_{closed|mid|open}.webp
```

= 3 면접관 × 눈 2상태 × 입 3상태(viseme). 프레임 구성이 파일명에 그대로 있다.

### C.2 현재는 1장만 쓴다

`Avatar.tsx:56-62`:

```tsx
/*
 * TODO: TTS가 phoneme/viseme 타임라인을 제공하면 아래 6개 프레임을
 * speechMarkIndex에 매핑한다.
 * eyes_open/closed x mouth_closed/mid/open = 총 6단계.
 * 현재는 안정적인 기본 표정(open + closed) 한 장만 표시한다.
 */
const imageSource = `/interviewers/${level}_eyes_open_mouth_closed.webp`;
```

`speaking`과 `speechMarkIndex`는 `aria-label`과 `data-speech-mark`에만 도달한다(`:67-69`). 렌더에 쓰이지 않는다.

`InterviewRoom.tsx:298`과 `:326`이 **`speechMarkIndex={0}` 하드코딩**으로 두 번(일반/PiP) 호출한다.

### C.3 에셋을 면접관별 폴더로 분리한다

요구사항이다. 파일명 규칙 암기 없이 면접관을 추가할 수 있게 된다.

```
public/interviewers/
  entry/   eyes_open_mouth_closed.webp  eyes_open_mouth_mid.webp  ... (6장)
  junior/  (6장)
  senior/  (6장)
```

`Avatar.tsx`의 경로 조립:

```tsx
const imageSource = `/interviewers/${level}/eyes_${eyes}_mouth_${mouth}.webp`;
```

`git mv`로 옮긴다. 참조하는 곳은 `Avatar.tsx:62` 한 줄뿐이다.

### C.4 눈 깜빡임 — TTS와 무관하게 지금 할 수 있다

눈은 발화와 관계없다. `speech_marks` 없이 즉시 구현 가능하다.

- 3~6초 간격 랜덤으로 `eyes_closed`를 100~150ms 표시.
- `design.md:222` "모션 감소 설정을 존중한다" → `prefers-reduced-motion: reduce`면 깜빡이지 않는다.
- `speaking`이 false일 때도 깜빡인다. 대기 중 완전 정지가 "얼어붙은 화면"으로 읽히는 것이 지금의 문제다.

### C.5 입모양 — Track 1의 `speech_marks`가 필요하다

**Track 1이 확정할 스키마:**

```json
{ "marks": [ { "mark": "w0", "time_ms": 0 }, { "mark": "w1", "time_ms": 240 } ] }
```

**중요한 한계 — Track 1이 명시한 것:** GCP TTS의 timepoint는 음소가 아니라 **SSML에 직접 심은 마크(어절 경계)** 단위다. 따라서 정확한 viseme 매핑은 불가능하다. 현실적 구현:

- 어절 구간 안에서 `mouth_mid` ↔ `mouth_open`을 짧은 주기로 교차, 어절 경계에서 `mouth_closed`.
- 발화가 끝나면 `mouth_closed` 고정.
- **`speech_marks_url`이 null이면 입모양을 움직이지 않는다.** Track 1의 TTS가 실패하면 `SpeechOutput.text_only=True`가 되고 `Avatar`는 이미 `textOnly` 분기로 "음성 없이 질문을 표시합니다"를 렌더한다(`Avatar.tsx:43-52`). 이 degrade 경로를 유지한다.

### C.6 오디오 재생 경로가 프론트에 없다

**조사에서 확인된 사실:** `speech_marks_url`은 서버가 `question.ready`로 내려보내지만(`live_handlers.py:547`), 프론트의 `parseQuestion`(`protocolClient.ts:292-299`)은 `question_turn_id` / `text` / `text_only`만 읽는다. `audio_url`도 읽지 않는다. `new Audio(...)`나 `HTMLAudioElement`가 지원자 SPA에 **하나도 없다.**

즉 **지금 TTS 음성은 브라우저에서 재생되지 않는다.** 입모양 작업의 선행 조건이 립싱크가 아니라 **오디오 재생 자체를 만드는 것**이다.

작업 순서:
1. `Question` 타입에 `audioUrl` / `audioExpiresAt` / `speechMarksUrl` 추가, `parseQuestion`에서 읽는다.
2. `InterviewRoom`에서 `audioUrl` 재생. `media.ts:113`의 `AudioContext`는 16kHz 캡처 전용이므로 재생은 별도 `HTMLAudioElement`를 쓴다 — 캡처 컨텍스트의 샘플레이트를 재생에 재사용하면 안 된다.
3. 재생 중 `audio.currentTime`을 `speech_marks`와 비교해 프레임을 고른다.
4. `speechMarkIndex={0}` 하드코딩 2곳을 실제 인덱스로 교체.

`Avatar.tsx`의 기존 테스트(`__tests__/interviewJourney.spec.tsx:122,126`)가 `speechMarkIndex={2}`와 `textOnly`를 검증하므로, 프레임 선택 로직에 대한 단위 테스트를 여기에 추가한다.

---

## D. 긴 면접의 컨텍스트

### D.1 `older_summary=""` 하드코딩

`interview_engine/application/interview_service.py:231`이 `self._context_builder.build(recent_turns=..., older_summary="", ...)`를 호출한다. 요약이 **한 번도 만들어지지 않는다.**

`interview_duration_minutes`는 10~120분(`criteria.py`)이다. 44분 면접이면 20턴 이상이 쌓이고, `recent_turns`만으로는 앞부분이 사라진다. 지원자가 10분 전에 말한 내용을 면접관이 모르는 상태가 된다.

**수정 방향:** N턴을 넘으면 오래된 턴을 요약해 `older_summary`에 넣는다. 요약은 Bedrock 호출이므로 **실시간 경로에 또 하나의 직렬 호출을 추가한다** — Track 1의 지연 예산과 충돌한다. 따라서:

- 요약은 **매 답변이 아니라 임계값 초과 시에만** 생성한다.
- 생성한 요약은 `DynamoRecentContext`(`interview_engine/adapters/recent_context.py`)에 캐시한다. 이미 최근 컨텍스트 저장소가 있다.
- 요약 생성 실패는 치명적이지 않게 한다 — 빈 문자열로 fallback하면 현행 동작이다.

### D.2 매 답변마다 임베딩

`live_handlers.py:439` `query_vector=None`.

`RetrievalClient`(`interview_engine/adapters/retrieval_client.py`)가 벡터를 받지 않으면 스스로 임베딩한다:

```python
if active_query_vector is None:
    if self._embedder is None:
        raise RuntimeError("semantic query embedder is unavailable")
    active_query_vector = self._embedder.embed(context, query, dimensions=1024)
```

**모든 답변에 Bedrock Titan 동기 호출이 하나 들어간다.** STT → 임베딩 → pgvector → Bedrock 질문생성 → TTS가 전부 직렬이다.

**이 항목은 측정 후에 판단한다.** Track 1이 구간별 p50/p95를 측정하므로, 임베딩이 실제로 병목인지 그 데이터로 결정한다. 지금 추측으로 캐싱을 넣으면 근거 없는 복잡도가 된다. Track 1의 측정 결과를 기다린다.

---

## E. RAG 흐름 — 확인된 사실 (수정 대상 아님)

이 트랙에서 **고치지 않는다.** 설계가 이미 옳고, 위 작업들이 이 흐름을 깨뜨리지 않았는지 확인하는 기준으로만 쓴다.

### E.1 검색

`submission_analysis/application/retrieval.py:12-15` `HybridRetrievalConfig`:

```python
vector_weight = 0.55
lexical_weight = 0.30
ownership_weight = 0.15
```

+ exact-symbol 보너스. `RetrievalClient(limit=5)`.

**`ownership_weight`는 현재 전원 0이다** — Track 4가 `candidate_identity_inputs`를 채우면 살아난다.

### E.2 질문 생성의 환각 방지

`question_prompt.py` 시스템 프롬프트 규칙 2: "질문 근거는 제공된 retrieved_sources의 발췌문에서만 가져옵니다."

그리고 **Python이 다시 검증한다** (`interview_service.py:283-289`):

```python
retrieved_by_id = {hit.source_id: hit for hit in retrieval.hits}
```

모델이 반환한 `source_reference_ids`를 실제 검색 결과와 교차 확인한다. 발췌는 `[:2000]`으로 절단.

### E.3 꼬리질문 결정은 LLM이 아니다

`interview_service.py:518-521`:

```python
follows_same_target = (
    question_target is not None
    and question_target.verification_target_id == answered_target.verification_target_id
)
```

같으면 `IN_PROGRESS` + `follow_up_count += 1`, 다르면 `COMPLETED`. `QuestionRationale.question_type`이 `"follow_up"` 또는 `"personalized"`로 기록된다.

다음 타깃 선택도 Python이다 (`interview_plan.py:83-104` `next_target_after_answer`) — 남은 시간이 0 이하면 None, 꼬리질문 예산이 남으면 같은 타깃, 아니면 다음 타깃. **시간 예산을 코드가 지킨다.**

### E.4 3개 degraded 모드

| 상황 | 결과 |
| --- | --- |
| 검색 실패 | `degraded_mode="search_fallback"`, "관련 자료를 불러오지 못해 공통 평가 질문으로 진행합니다." |
| 검색 결과 0 | `degraded_mode="search_no_result"` |
| 질문 생성 실패 | 세션 `PAUSED` + `degraded_modes += "question_generation"` |

**이 3개 경로를 깨뜨리지 않는다.** 특히 `PAUSED`는 면접을 중단하지 않고 재개 가능하게 만드는 장치다(`InterviewResumeView`).

---

## F. 완료 기준

1. 발송된 `invitation_url`이 `/access/{token}` 경로 형태이고, 토큰이 쿼리 스트링에 없다.
2. 그 URL로 접속 → exchange 성공 → 본인 확인 단계로 진행되는 통합 테스트가 있다 (URL 생성과 소비를 같은 테스트가 잇는다).
3. `applicant_access_base_url`에 기본값이 없다.
4. `InterviewSessionView.interview_level`이 있고, 프론트가 URL 쿼리 대신 이 값을 읽는다.
5. `?level=senior`를 붙여도 아바타가 바뀌지 않는다.
6. `Avatar` `level` prop이 필수다 (기본값 없음).
7. 에셋이 `public/interviewers/{level}/`로 분리됐다.
8. 눈 깜빡임이 동작하고 `prefers-reduced-motion`을 존중한다.
9. `Question` 타입이 `audioUrl` / `speechMarksUrl`을 읽고, TTS 음성이 브라우저에서 재생된다.
10. `speech_marks`가 있으면 입모양이 움직이고, null이면 `mouth_closed` 고정이다.
11. `speechMarkIndex={0}` 하드코딩이 남아 있지 않다.
12. `textOnly` degrade 경로가 그대로 동작한다.
13. `older_summary`가 임계값 초과 시 채워지고, 실패 시 빈 문자열로 fallback한다.
14. RAG의 3개 degraded 모드와 `source_reference_ids` 교차검증이 그대로 통과한다.
15. `npm run typecheck` / `npm test` / `npm run build` 통과, `contracts:generate` 결과가 커밋됐다.
