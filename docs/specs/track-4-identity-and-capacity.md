# Track 4 — 지원자 식별 + 예약 기반 용량 관리

**목표:** (1) GitHub 저장소에서 지원자 본인이 쓴 코드를 식별한다. (2) 면접 예약 시각을 기준으로 Worker/API를 미리 띄우고 끝나면 내린다. (3) 동시 인원별 필요 태스크 수를 산정한다.

**전제:** 오너십 백엔드는 이미 90% 만들어져 있다. 새로 만드는 것은 contributor 조회 엔드포인트 하나와 프론트 드롭다운, 그리고 인프라의 스케줄 액션이다.

**다른 트랙과의 겹침:** 오너십 결과를 **화면에 보여주는 일은 Track 2**(6장)로 넘겼다. 이 트랙은 값을 채우는 데까지만 책임진다. 용량 산정의 지연 입력은 Track 1의 측정값이 필요하다.

---

# 1부 — GitHub 지원자 식별

## 1.1 이미 만들어져 있는 것

경로가 끝까지 뚫려 있다. 값만 비어 있다.

```
SubmissionCreate.candidate_identity_inputs        submission_analysis/api/applicant_routes.py
  → _normalize_candidate_identity_inputs(...)     application/submission_service.py:303
  → Submission.candidate_identity_inputs (JSON)   DB 컬럼
  → CommitIdentityInput.model_validate(...)       workers/analysis/pipeline.py:357
  → GitHubPublicTransport.fetch(..., identity=)   workers/analysis/git_fetch.py
      → _authored_pool: GitHub author 필터로 재조회
  → classify_commit_ownership(...)                submission_analysis/domain/git_analysis.py
  → GitRepositoryAnalysis.ownership_*             DB
  → HybridRetriever ownership_weight = 0.15       application/retrieval.py:15
```

`pipeline.py:357`의 주석이 의도를 명시한다: "The identity is resolved before the fetch so the transport can ask GitHub for this candidate's commits."

`git_fetch.py`의 `_authored_pool` docstring: "GitHub's `author` filter takes one login or address at a time, so the claimed identities are tried in turn and the first that matches wins."

**받는 형식** (`_normalize_candidate_identity_inputs`, `submission_service.py:303-315`):

```python
if not isinstance(raw_values, list) or not all(isinstance(v, str) for v in raw_values):
    raise ValueError("candidate identity inputs must be string arrays")
```

→ **모든 값이 문자열 배열이어야 한다.** 페이로드 형태:

```json
{ "claimed_handles": ["octocat"], "claimed_emails": ["octocat@example.com"] }
```

## 1.2 지금 비어 있는 곳 — 정확히 한 줄

`apps/applicant-interview/src/app/routeAdapters.tsx`:

```tsx
candidate_identity_inputs: {},
```

**빈 dict가 들어가므로 오너십은 전원 `CONTEXT_ONLY`이고, `ownership_weight = 0.15`는 항상 0으로 곱해진다.** RAG의 15%가 죽어 있다.

*(2026-08-20: 이 문서가 적었던 `:213`은 낡았다 — `origin/develop` 기준으로 `:256`이다. 이 파일은 자주 움직이므로 줄번호가 아니라 문자열로 grep할 것.)*

이 한 줄을 채우는 것이 오너십 화면 표시(Track 2 §6)의 선행 조건이다. 값이 없으면 표시할 것도 없고 검증할 것도 없다 — 그 조사 결과는 `track-2-handover.md` 5.1에 정리돼 있다(오너십 클래스가 검색 인덱스·`question_source_references`·타임라인 투영 세 곳에서 끊긴다는 것, 그리고 `resolve_source_reference`가 프로덕션에서 호출되지 않는다는 것).

## 1.3 새로 만드는 것 — contributor 조회

`git_fetch.py` 전체를 grep했으나 `contributors` 호출이 **없다.** 이것이 유일한 신규 백엔드다.

```
GET /v1/applicant/repository-contributors?repository_url=...
```

- 인증: 기존 `applicant_scope`(쿠키 `iep_applicant_session`) 재사용. `applicant_routes.py`의 다른 라우트와 동일.
- **`validate_public_url(url, "PUBLIC_GIT")`을 반드시 통과시킨다** (`submission_validator.py:49-80`) — https 전용, URL 자격증명 금지, `token`/`key`/`secret`/`password` 쿼리 키 거부, localhost·비글로벌 IP 거부, github.com/gitlab.com/bitbucket.org 허용목록. 새 엔드포인트가 SSRF 구멍이 되는 것을 막는다.
- `_github_repository(url)`(`git_fetch.py`)로 owner/repo를 파싱한다 — https + hostname `github.com` + 경로 2조각을 이미 강제한다.
- `GitHubPublicTransport._headers()`를 재사용한다. `Authorization: Bearer`가 토큰이 있을 때만 붙고, **토큰은 헤더에만 놓인다** (`git_fetch.py:160` 원칙).
- 호출: `GET {api_root}/contributors?per_page=100`. `login` / `avatar_url` / `contributions`만 반환한다.
- **GitLab / Bitbucket:** `validate_public_url`은 셋을 허용하지만 `_github_repository`는 github만 받는다. GitHub이 아니면 빈 목록을 반환하고 프론트는 수동 입력으로 fallback한다. 이 트랙에서 GitLab API를 구현하지 않는다.

레이트리밋은 이미 문서화돼 있다 (`GitHubPublicTransport` docstring): 비인증 60/시간, 인증 5000/시간. contributor 조회가 저장소당 요청 1개를 더 쓴다. 지원자당 최대 3개 저장소(`MAX_PUBLIC_GIT_PROJECTS = 3`, `submission_service.py:139`)이므로 지원자당 +3이다. 비인증 60/시간이면 **시간당 20명이 상한**이다 — `GITHUB_TOKEN`이 이미 `task_secrets`에 있으므로(`prod/main.tf:207`) 이 엔드포인트도 토큰 경로를 타야 한다.

## 1.4 login에는 이메일이 없다 — 이 트랙의 실제 난점

`classify_commit_ownership`의 가중치:

```
name 0.35 + email 0.45 + handle 0.20,  0.9 상한
PRIMARY_OWNED ≥ 0.7 / SHARED ≥ 0.4 / else CONTEXT_ONLY
```

GitHub `contributors` 응답에는 `login`만 있고 **이메일이 없다.** 지원자가 드롭다운에서 자기 login을 골라 `claimed_handles: ["octocat"]`만 채우면 점수는 **0.20**이다. `SHARED` 문턱 0.4에도 못 미친다.

**즉 드롭다운만 붙이면 오너십은 여전히 전부 `CONTEXT_ONLY`이고, 기능이 아무것도 바꾸지 않는다.**

**해결:** 선택된 login의 커밋에서 author 이메일을 역수집해 `claimed_emails`를 채운다.

```
GET {api_root}/commits?author={login}&per_page=100
  → commit.author.email 수집 → 중복 제거 → claimed_emails
```

- `noreply@github.com` 계열은 걸러낸다 (`{id}+{login}@users.noreply.github.com`) — 실제 커밋 이메일이 아니라 프라이버시 프록시다. **다만 `claimed_handles` 매칭에는 login이 들어 있으므로 이 주소를 버려도 손실이 없다.**
- 이 조회를 **contributor 조회 엔드포인트에서 함께** 할지, **분석 워커에서** 할지 결정해야 한다. **워커에서 한다.** 이유: 프론트가 이메일 목록을 받으면 다른 지원자의 이메일이 브라우저에 도달한다. 워커는 이미 `_authored_pool`에서 login별 재조회를 하고 있으므로 자연스러운 위치다.
- 따라서 **프론트는 `claimed_handles`만 보낸다.** 워커가 `claimed_emails`를 채워 `classify_commit_ownership`에 넘긴다. `CommitIdentityInput`이 두 필드를 모두 갖고 있어 구조 변경이 없다.

이렇게 하면 name 0.35 + email 0.45 + handle 0.2가 모두 살아나 `PRIMARY_OWNED`에 도달할 수 있다.

## 1.5 프론트 — 드롭다운

`apps/applicant-interview/src/features/submissions/index.tsx`의 `RepositorySubmissionEditor`를 확장한다. 현재 구조:

```tsx
const MAX_PROJECT_URLS = 3;
const [repositoryUrls, setRepositoryUrls] = useState<string[]>([""]);
// 입력: label `저장소 URL {index+1}`, id `public-repository-url-${index}`,
//       placeholder "https://github.com/organization/project"
// 추가/삭제 아이콘 버튼, 그리고 registerRepository가 URL마다 순차 등록
```

추가할 것 — **URL 하나당 contributor 선택 상태 하나:**

1. URL 입력이 유효한 github URL 형태가 되면 contributor를 조회한다. **자동 조회가 아니라 "작업자 목록 불러오기" 버튼으로 한다.** `design.md:100`의 제출 화면 규칙("자동 진행 없음", 스피너 금지)에 맞고, 오타 URL로 레이트리밋을 태우지 않는다.
2. `<select>`로 login 목록을 렌더한다. `contributions` 내림차순. `avatar_url`은 붙여도 되고 생략해도 된다.
3. **"목록에 없음 / 직접 입력"** 옵션을 반드시 둔다. 커밋 author가 다른 계정인 경우, 조직 저장소에서 fork로 기여한 경우, contributor API가 상위 N명만 주는 경우가 있다.
4. **선택은 필수로 만들지 않는다.** 선택하지 않으면 지금과 같은 `{}`이 가고 `CONTEXT_ONLY`로 분석된다 — 현행 동작이므로 회귀가 없다. 제출을 막으면 저장소 하나 때문에 지원자가 진행 못 하는 상태가 된다.
5. `registerRepository(url, "projects")` 시그니처에 identity를 추가한다:

```tsx
await api.registerRepository(url, "projects", { claimed_handles: [login] })
// routeAdapters.tsx:213 의 candidate_identity_inputs: {} 를 이 값으로 교체
```

`SubmissionCreate`가 `extra="forbid"`이므로 필드명을 정확히 `candidate_identity_inputs`로 맞춘다.

## 1.6 사람이 검증해야 한다

`classify_commit_ownership`은 `requires_verification` 플래그와 `explanation_codes`를 만든다. **지원자의 자기 신고를 사실로 취급하지 않는다.** 지원자가 남의 login을 고르면 그 사람의 커밋이 지원자 것으로 분석된다.

- 오너십 분류와 `requires_verification`을 담당자 화면에 노출하는 것은 **Track 2 6장**이다.
- 이 트랙은 `claimed_*`가 **지원자 주장**이라는 사실이 필드명과 저장 값에 남아 있게 유지한다 — 이미 `claimed_`라는 접두사가 그 일을 하고 있다. 이름을 바꾸지 않는다.

## 1.7 검증

- 실제 다인 저장소로: contributor 목록이 오고, 본인 login 선택 → 워커가 이메일을 역수집 → `ownership_classification`이 `PRIMARY_OWNED` 또는 `SHARED`로 나오는지 확인.
- 아무것도 선택하지 않은 경우 현행과 동일하게 `CONTEXT_ONLY`로 분석되는지 확인 (회귀 테스트).
- `validate_public_url`이 거부하는 URL(localhost, `?token=`, http)로 조회 시 400.
- **GitHub 토큰이 응답 본문·로그·에러 메시지에 없음**을 검증하는 테스트.

---

# 2부 — 예약 기반 Worker 실행/종료

## 2.1 예약 시각은 저장되고 아무도 읽지 않는다

`interview_at`은 UI부터 DB까지 완전히 배선돼 있다:

```
InterviewDesigner.tsx:196   datetime-local 입력
  안내문: "예약된 시각을 기준으로 면접 실행 환경을 준비합니다."   ← 준비하지 않는다
  → hiring/types.ts:123     interviewAt: ""
  → Position.interview_at: datetime | None    (company.py:~130)
  → company_service.py / postgres.py          저장
```

`interview_capacity`(`동시에 시험을 진행할 수 있는 지원자 수`, `InterviewDesigner.tsx:175-190`)와 `headcount`(`Field(ge=1, le=10_000)`)도 같다. **셋 다 쓰이는 곳이 없다.** UI 안내문이 사실이 아니다.

## 2.2 스케줄 액션이 하나도 없다

`infra/modules/compute/main.tf`에 있는 것:

```hcl
aws_appautoscaling_target      # api: min 2 / max 20,  worker: min 1 / max 30
aws_appautoscaling_policy      # TargetTrackingScaling, ECSServiceAverageCPUUtilization
                               # api 60%, worker 65%
```

`aws_appautoscaling_scheduled_action`이 **레포 전체에 없다.** prod는 `api_desired_count = 4`, `worker_desired_count = 4`로 24시간 고정이다(`prod/main.tf:150-160`).

`lifecycle { ignore_changes = [desired_count] }`가 두 서비스에 이미 걸려 있어, **오토스케일링이 바꾼 태스크 수를 다음 `terraform apply`가 되돌리지 않는다.** 스케줄 액션을 넣기에 필요한 전제가 이미 갖춰져 있다.

## 2.3 CPU 타깃트래킹은 이 워크로드를 못 잡는다

실시간 면접의 병목은 CPU가 아니다. 한 답변에 STT → 임베딩 → pgvector → Bedrock → TTS가 **직렬 네트워크 대기**로 일어난다(Track 1의 6장). 태스크는 대기 중 CPU를 거의 쓰지 않으므로, **CPU 60%에 도달하기 전에 응답 지연이 먼저 무너진다.**

**바꿀 것:**

| 서비스 | 현재 | 이후 |
| --- | --- | --- |
| api | CPU 60% | `ALBRequestCountPerTarget` 또는 활성 WebSocket 연결 수 기반 커스텀 지표 |
| worker | CPU 65% | SQS `ApproximateNumberOfMessagesVisible` / 태스크 수 (커스텀 지표 타깃트래킹) |

CPU 정책은 **안전망으로 남긴다.** 두 정책을 함께 두면 더 공격적인 쪽이 이긴다.

## 2.4 실시간 면접은 Worker가 아니라 API가 받는다 — 요구사항의 전제 수정

요구는 "면접 처리용 AWS Worker가 24시간 실행"인데, 코드는 다르다.

- **실시간 면접은 API 서비스의 WebSocket 핸들러**가 처리한다 (`live_handlers.py`, `handle_audio`). 예약 시각에 늘려야 하는 것은 **API**다.
- **Worker는 면접이 끝난 뒤 몰린다.** `EVENT_QUEUE_ROUTING`(`runtime/worker.py:51-66`)이 15개 이벤트를 4개 큐(analysis / media / reporting / deletion)로 보내고, 리포트 생성·미디어 처리는 면접 종료 이후 작업이다.

**즉 두 서비스의 피크가 시간대가 다르다.** API는 예약 시각 전에, Worker는 예약 시각 이후에 올려야 한다. 하나의 스케줄로 둘을 같이 움직이면 둘 다 틀린다.

## 2.5 Worker를 0으로 내릴 수 없다

Worker는 면접 큐만 먹지 않는다. `deletion` 큐가 **보존기간 만료 삭제**를 처리하고, 이것은 EventBridge 규칙이 밀어 넣는다:

```hcl
# infra/modules/async-workflow/main.tf:93
aws_cloudwatch_event_rule.retention
  source      = "interview-evidence.company-management"
  detail-type = "retention.expired"
  → aws_cloudwatch_event_target.retention → aws_sqs_queue.work["deletion"]
```

**Worker를 0으로 내리면 보존기간 삭제와 리포트 생성이 멈춘다.** 삭제 지연은 법적 약속을 어기는 것이고, 리포트 지연은 담당자가 결과를 못 보는 것이다.

**따라서:**
- Worker `min_capacity`는 **0이 아니다.** 현재 1이 하한이고, 그것을 유지한다. 큐가 비어 있으면 롱폴링으로 대기하므로 태스크 1개의 비용이 절약의 기준선이다.
- prod의 `worker_desired_count = 4`를 **1로 낮추고 큐 깊이 기반으로 올린다.** 24시간 4개가 진짜 낭비다. 0이 아니라 4→1이 이 요구사항의 실제 절약이다.
- 더 내리고 싶다면 **면접 임계 큐(analysis/reporting)와 배경 큐(deletion/media)를 다른 서비스로 분리**해야 한다. 이 트랙 범위 밖으로 남기고, 필요성이 측정으로 증명된 뒤 결정한다.

## 2.6 스케줄 액션 — 정적 스케줄부터

`aws_appautoscaling_scheduled_action`은 cron 문자열이므로 **Terraform 시점에 알아야 한다.** 개별 면접 예약(`Position.interview_at`)은 런타임 데이터라 Terraform으로 못 만든다.

두 단계로 나눈다.

**1단계 — 근무시간 스케줄 (지금 한다):**

```hcl
resource "aws_appautoscaling_scheduled_action" "api_business_hours_up" {
  schedule = "cron(30 8 ? * MON-FRI *)"   # KST 17:30 → UTC 08:30
  scalable_target_action { min_capacity = 4, max_capacity = 20 }
}
resource "aws_appautoscaling_scheduled_action" "api_business_hours_down" { ... min_capacity = 2 ... }
```

- **`min_capacity`를 움직이고 `desired_count`를 직접 쓰지 않는다.** 타깃트래킹과 desired를 동시에 다투면 서로를 되돌린다. 스케줄이 바닥을 올리고, 타깃트래킹이 그 위에서 실제 수를 정한다.
- 타임존은 `cron`이 UTC다. **KST 변환을 주석에 반드시 적는다.** 이것이 조용히 9시간 틀리는 전형적인 자리다.
- Worker는 같은 스케줄을 **면접 종료 이후로 밀어서** 적용한다(2.4).

**2단계 — 예약 기반 (측정 후):**

`interview_at`을 읽어 스케줄 액션을 만들려면 런타임 컴포넌트가 필요하다. 후보:
- EventBridge Scheduler one-time 스케줄을 애플리케이션이 생성 → Lambda가 `RegisterScalableTarget`으로 `min_capacity`를 올린다.
- 또는 outbox 이벤트(`interview.scheduled`)를 추가해 Worker가 예약 테이블에 넣고, 주기 Lambda가 다음 N분 예약을 보고 바닥을 올린다.

**둘 다 새 IAM 권한(`application-autoscaling:*`)과 새 컴포넌트를 요구한다.** 1단계로 절약의 대부분을 얻고, 그 실측 절감액을 보고 2단계를 정한다. **먼저 1단계를 배포한다.**

## 2.7 사전 접속은 이미 가능하다 — 확인만 한다

요구 2번("지원자가 면접 시작 전에도 접속하여 마이크·카메라 테스트, 정보 입력")은 이미 구현돼 있다.

`ApplicantAccess` 단계: `exchange` → `identity` → `equipment`(장비 점검) → `submissions` → 면접. `InterviewSessionCreate`가 `equipment_check_id`를 요구하므로 **장비 점검이 세션 생성의 선행 조건**이다.

**따라서 API 태스크를 예약 시각에 올린다는 것은 "그 전엔 접속 불가"를 뜻하지 않는다.** 사전 단계는 가벼운 HTTP이고 최소 태스크 2개로 처리된다. 무거운 것은 WebSocket 면접뿐이다. 이 구분을 스케줄 근거로 문서에 남긴다.

## 2.8 Worker 준비 확인 — 기존 게이트를 쓴다

요구 4번("Worker가 준비된 이후 실제 면접 세션 시작"). 새 헬스체크를 만들지 않는다.

- ALB 타깃그룹 헬스체크와 ECS `health_check_grace_period`가 이미 준비된 태스크에만 트래픽을 보낸다.
- 세션 생성은 `equipment_check_id` 게이트를 이미 통과해야 한다.
- 추가로 필요한 것은 **면접 시작 버튼이 눌렸을 때 용량이 부족하면 명확히 실패하는 것**이다. 지금은 WebSocket 연결이 조용히 느려진다. `interview_capacity`(2.1의 죽은 필드)를 여기서 처음으로 읽어 **동시 세션 수 상한**으로 쓴다 — 초과 시 대기 안내를 반환한다. 죽은 필드에 의미를 주는 가장 작은 방법이다.

---

# 3부 — 동시 인원별 용량 산정

## 3.1 지금 표를 만들 수 없다 — 그리고 그것이 이 트랙의 결론이다

요구는 "동시 100명이면 태스크 몇 개, 200명이면, 500명이면"이다. 이 표를 **추측으로 쓰면 안 된다.** 근거 없는 숫자를 인프라에 넣으면 그 숫자가 이후 모든 판단의 기준이 되고, 아무도 출처를 모른다.

필요한 입력:
- **태스크 1개가 감당하는 동시 WebSocket 세션 수** — Track 1이 측정하는 구간별 p50/p95 없이는 계산 불가. 직렬 지연이 4초면 태스크당 동시 세션 수가 1초일 때의 1/4이다.
- **답변 1건당 외부 호출 수와 각 호출의 대기 시간** — GCP 이관으로 STT 경로가 근본적으로 바뀐다(120초 폴링 → 인라인 recognize). **이관 전 수치로 표를 만들면 그 표는 배포 첫날 무효다.**

**따라서 순서는: Track 1 이관 → 부하 테스트 → 표.** 이 트랙은 부하 테스트 시나리오와 관측 지점을 준비하는 것까지 한다.

## 3.2 ECS가 먼저 막히지 않는다 — 진짜 상한들

태스크를 늘려도 아래가 먼저 터진다. 표를 만들 때 **ECS 태스크 수만 적으면 틀린다.**

| 상한 | 위치 | 100/200/500명에서 |
| --- | --- | --- |
| Aurora Serverless v2 ACU | dev 0.5–8, prod 2–64 | pgvector 검색 + 트랜잭션 outbox. 500명 동시면 prod 상한 재검토 필요 |
| Bedrock 리전 쿼터 | 계정/리전별 TPM·RPM | 답변마다 Claude 1회 + Titan 1회. **쿼터 증액은 신청·승인이 걸리므로 가장 긴 리드타임** |
| GCP STT 쿼터 | 프로젝트별 스트리밍 동시 수 | Track 1의 C-2가 스트리밍으로 가면 여기가 새 상한이 된다 |
| NAT Gateway | dev는 `nat_gateway_per_az = false` → **NAT 1개 공유** | 모든 GCP·Bedrock 아웃바운드가 한 NAT를 지난다. dev에서 부하 테스트하면 여기가 먼저 막혀 잘못된 결론을 준다 |
| DynamoDB (멱등성·최근 컨텍스트) | 온디맨드면 문제 없음 | 프로비저닝이면 확인 필요 |
| SQS | 실질 무제한 | 상한이 아니다 |

**부하 테스트는 prod와 같은 NAT 구성에서 해야 한다.** dev의 단일 NAT에서 얻은 숫자로 prod 표를 만들면 과소 산정된다.

## 3.3 표가 갖춰야 할 형태

측정 후 채운다. 빈 칸을 남긴 채로 커밋한다 — **추측값을 채워 넣지 않는다.**

| 동시 세션 | api 태스크 | worker 태스크 (면접 중) | worker 태스크 (종료 후 피크) | Aurora ACU | 확인한 Bedrock TPM |
| --- | --- | --- | --- | --- | --- |
| 100 | ? | ? | ? | ? | ? |
| 200 | ? | ? | ? | ? | ? |
| 500 | ? | ? | ? | ? | ? |

"종료 후 피크" 열이 별도인 이유는 2.4다 — 리포트 생성은 면접이 끝난 뒤 몰린다. 100명이 동시에 끝나면 리포트 요청 100건이 한꺼번에 `reporting` 큐에 들어간다.

현재 `max_capacity`는 api 20 / worker 30이다. 산정 결과가 이를 넘으면 **`max_capacity`도 올려야 한다** — 스케줄만 넣고 상한을 그대로 두면 조용히 상한에 걸린다.

## 3.4 부하 테스트 시나리오

- 실제 WebSocket 프로토콜을 쓴다. HTTP만 때리면 무의미하다 — 병목이 WebSocket 세션 수명 안의 직렬 호출이다.
- 오디오는 `pcm_s16le / 16000 / 1`(Track 1의 4.5에서 상수로 못박은 값)로 보낸다.
- 계측 지점: `shared/operations.py`의 `MetricRecorder` — Track 1이 구간별로 심어 둔 것을 그대로 읽는다.
- 관측할 것: p95 답변 왕복 시간, WebSocket 연결 실패율, SQS `ApproximateAgeOfOldestMessage`, Aurora ACU, Bedrock throttle 횟수.
- **throttle이 0이 아니면 태스크를 더 늘려도 무의미하다.** 이 지점을 먼저 찾는 것이 부하 테스트의 목적이다.

---

## 4. 완료 기준

**1부 — 식별**
1. `GET /v1/applicant/repository-contributors`가 있고 `applicant_scope` 인증과 `validate_public_url`을 통과한다.
2. GitHub 토큰이 응답·로그·에러에 나타나지 않음을 테스트가 검증한다.
3. 드롭다운에 "직접 입력" 옵션이 있고, 선택하지 않아도 제출된다.
4. `routeAdapters.tsx:213`의 `candidate_identity_inputs: {}`가 실제 값으로 교체됐다.
5. 워커가 선택된 login의 커밋에서 author 이메일을 역수집해 `claimed_emails`를 채운다.
6. 실제 다인 저장소에서 `ownership_classification`이 `CONTEXT_ONLY`가 아닌 값으로 나온다 — **이것이 이 기능이 실제로 동작했는지의 유일한 증거다.**
7. 미선택 시 `CONTEXT_ONLY`로 분석되는 회귀 테스트가 있다.

**2부 — 용량 관리**
8. `aws_appautoscaling_scheduled_action`이 api·worker에 존재하고 **`min_capacity`만** 조정한다.
9. cron이 UTC이고 KST 변환이 주석에 있다.
10. api는 요청/연결 기반, worker는 SQS 큐 깊이 기반 타깃트래킹이 있고 CPU 정책은 안전망으로 남았다.
11. worker `min_capacity`가 0이 아니고, 그 이유(deletion/reporting 큐)가 코드 주석에 있다.
12. prod `worker_desired_count`가 4에서 낮춰졌다.
13. `interview_capacity`가 동시 세션 상한으로 실제로 읽히고, 초과 시 명확한 응답이 나간다.
14. `InterviewDesigner.tsx:196`의 안내문("예약된 시각을 기준으로 면접 실행 환경을 준비합니다")이 사실이 됐거나, 사실이 될 때까지 문구가 수정됐다.
15. `make infra-format-check` / `make infra-validate` 통과, `test_terraform_contracts.py`에 스케줄 액션 존재 assert가 추가됐다.

**3부 — 산정**
16. 3.3의 표가 파일로 존재하고, **측정값으로만** 채워졌다(빈 칸은 빈 칸으로 남는다).
17. 부하 테스트가 prod와 동일한 NAT 구성에서 수행됐다.
18. Bedrock TPM·GCP STT 쿼터의 현재값이 확인·기록됐고, 증액이 필요하면 신청됐다.
19. 산정 결과가 `max_capacity`(api 20 / worker 30)를 넘는지 판단됐다.
