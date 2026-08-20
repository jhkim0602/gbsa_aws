# Track 2 인계 — 가중 점수 산출을 다른 작업 위에 얹는 방법

**이 문서의 목적:** Track 2(점수 산술 + 검토 화면)에서 무엇을 바꿨는지, 그리고 그것을 **다른 사람이 진행한 결과와 합칠 때 무엇을 깨뜨리지 않아야 하는지** 적는다. 명세는 `track-2-scoring-and-review.md`이고, 이 문서는 그 명세를 구현한 결과의 인계다.

**작업 브랜치:** `feature/scoring-arithmetic` (`origin/develop` 기준)
**기준 커밋:** `84af2d4 Merge pull request #4 from jhkim0602/bugfix/interview-room-flow`

**검증 상태 (2026-08-20, `origin/develop` 병합 후 + 8장의 결함 3건 수정 후)**

| 항목 | 결과 |
| --- | --- |
| `pytest` (= `testpaths`, `npm test`가 돌리는 것) | **206 통과** |
| vitest `company-console` / `applicant-interview` | **84 / 23 통과** |
| `mypy backend/src` (172 파일) | 통과 |
| `ruff check` / `ruff format` | 통과 |
| `scripts/check_module_boundaries.py` / `check_migrations.py` | 통과 (head 1개, `m_014_report_scoring`) |
| `tsc -b` / `eslint` / `npm run build` | 통과 |
| `backend/tests/integration/migrations/` | 10 통과 / 1 실패 |

마지막 1건은 착수 전부터 빨간 `test_indexes_match_the_migrations`다 — ORM이 선언한 `ix_submissions_invitation_material`을 만드는 마이그레이션이 없는 Lane B의 기존 드리프트이고, 점수와 무관하다. 자세한 기준선은 명세 9.2에 있다.

**단위 테스트만으로는 부족했다.** 위 표가 전부 초록인 상태에서도 로컬 스택으로 실제 화면을 열자 500·422가 나왔다. 무엇이었고 왜 테스트가 놓쳤는지는 8장에 있다. 다음 사람은 **9장의 로컬 확인 절차를 반드시 한 번 돌리기 바란다.**

---

## 1. 한 문장 요약

기업이 설정한 가중치가 실제로 점수에 반영되고, 그 산술이 리포트에 **동결**되며, 검토자가 `55.7 ÷ 0.75 = 74`를 화면에서 그대로 읽을 수 있게 됐다.

이전에는 `EvaluationCriterion.weight`가 저장되고 위저드에서 편집되지만 **읽는 채점 코드가 하나도 없었다**. 점수는 두 번의 단순 평균이었다.

---

## 2. 무엇이 바뀌었나

### 2.1 새 파일 (5개)

| 파일 | 역할 |
| --- | --- |
| `backend/src/interview_evidence/shared/assessment_axes.py` | 채점축 5개의 키·라벨. Lane A가 가중치를 검증하고 Lane D가 채점하는 데 **같은 키 집합**을 써야 해서 `shared`에 뒀다 — `interview_level.py`와 같은 이유(의존 방향 역전 방지) |
| `backend/src/interview_evidence/reporting/domain/scoring.py` | 순수 산술 `aggregate()`. 점수만이 아니라 **분자·분모·제외 목록**을 함께 반환한다 |
| `backend/alembic/versions/integration/i_013_competency_axis_weights.py` | `competency_model_versions.axis_weights` (JSON, `DEFAULT '{}'`) |
| `backend/alembic/versions/integration/i_014_report_scoring_inputs.py` | `reports.overall_score`·`scoring_inputs`, `report_items.criterion_weight`·`axis_weights` |
| 단위 테스트 4개 | `test_axis_weights.py`, `test_weighted_scoring.py`, `test_report_view_contract.py`, `test_invitation_score_projection.py` |

### 2.2 계층별 변경

```
[설정]  EvaluationDesigner.tsx  →  03 채점축 섹션 (슬라이더 5개 + 자동 재분배)
           ↓ axis_weights (합계 100)
[Lane A] CompetencyModelVersion.axis_weights  +  validator 4종
           ↓ CriterionVersionSnapshot.axis_weights  (경계)
[Worker] ReportGenerator  →  ReportItem.criterion_weight · axis_weights 로 스냅샷
           ↓
[Lane D] scoring.aggregate()  →  average_score · overall_score 가 가중평균
           ↓ reports.scoring_inputs 에 동결
[API]    /report → scoring_breakdown (numerator / denominator / contributions / exclusions)
         /positions/{id}/invitations → overall_score · scored/total_criteria_count
           ↓
[화면]   ReportView 계산기 · PositionInvitations 순위 열
```

### 2.3 결정: 가중치 합계는 100

두 방식이 **같은 점수를 낸다**. 다른 것은 담당자가 읽는 숫자의 의미뿐이다.

- **채택:** 합계 100 강제 + UI 자동 재분배 → 화면의 `30`이 곧 30%
- 폐기: 합계 자유 + 채점 시 정규화 → `30`이 40%일 수 있어 UI가 계속 설명해야 한다

이 결정은 다른 작업자가 `criteria_service.create_version`에 넣어 둔 `must total 100` 검증과 같은 방향이었고, **그 검증을 도메인으로 올려 한 곳으로 합쳤다**(`CompetencyModelVersion.criterion_weights_total_100`). 두 곳에 흩어져 있으면 규칙이 갈라진다.

축 가중치도 같은 규칙을 따른다(5개 합계 100). 슬라이더는 `rebalanceAxisWeights`가 나머지 비율을 보존하며 재분배한다.

### 2.4 계산기가 분모를 보여주는 이유

이 트랙의 핵심 설계 판단이다. `"근거 부족 → 미채점"`과 `"고정 가중치"`는 **분모를 드러내지 않으면 합성되지 않는다.**

기준 D(25%)가 채점 불가로 빠지면 남은 가중치 합은 0.75이고 점수는 `55.7 ÷ 0.75 = 74`다. 화면에 `74`만 있으면 담당자는 그것이 **100% 중 74인지 75% 중 74인지 알 수 없다.** 추적성을 만들려는 작업이 추적성을 깨뜨린다.

**설정 합계와 채점 분모는 다른 것이다.** 설정은 항상 100이지만, 면접이 닿지 못한 기준이 빠지면서 실제로 센 가중치는 0.75가 될 수 있다. 그래서 분모를 저장하고 렌더한다.

---

## 3. 합칠 때 되돌리면 안 되는 것 6가지

병합·리베이스 과정에서 사라지기 쉽고, 사라져도 **오류 없이 조용히 틀린 값**이 되는 것들이다.

### 3.1 `CompetencyInsights.tsx`의 클라이언트 재계산은 제거된 상태여야 한다

`applyConfiguredWeights`가 브라우저에서 종합 점수를 다시 계산하고 있었다. 되살리면 두 가지가 깨진다.

1. **동결이 무효화된다.** 서버는 리포트가 동결한 가중치로 계산해 보낸다. 화면에서 다시 계산하면 기업이 가중치를 바꿨을 때 과거 점수가 달라진다 — 이 트랙 전체가 막으려던 버그다.
2. **서버와 숫자가 달라진다.** 조인이 `code === criterionId`(코드 대 UUID, 프로덕션에서 절대 매칭 안 됨) → `name === criterionName` 폴백이다. 기준 이름이 바뀌면 그 기준이 빠져 **브라우저는 부분집합 평균, 서버는 전체 평균**이 된다.

기준별 `weight` 조인은 남겨 뒀다(차트가 쓴다). 관련 테스트: `competencyInsights.test.ts`의 `leaves the overall score to the server, ...`.

### 3.2 마이그레이션은 `integration/` 단일 체인에 붙인다

```
i_013_competency_axis_weights.py   revision m_013_axis_weights    ← down: m_012_position_interview
i_014_report_scoring_inputs.py     revision m_014_report_scoring  ← down: m_013_axis_weights
```

`reporting/d_00N`에 두면 안 된다. `d_001_reporting`은 `branch_labels=("reporting",)`인 **레인 브랜치 루트**이고 네 레인은 이미 `merge_001_lane_heads`에서 합쳐졌다. 그 뒤에 새 리비전을 달면 **이미 병합된 브랜치에서 두 번째 head가 갈라져** 다시 합쳐지지 않는다. 선례는 `i_010_report_item_axis_scores`(같은 Lane D 컬럼 추가가 `integration/m_010`으로 들어갔다).

리비전 id는 **32자 이하**여야 한다(`alembic_version.version_num`이 `varchar(32)`, sqlite는 초과를 조용히 받아들여 첫 실제 Postgres upgrade에서 실패). `scripts/check_migrations.py`와 `test_revision_ids.py`가 강제한다.

`test_lane_merge.py`는 head를 하드코딩하던 것을 **스크립트에서 유도하도록 고쳤다**(`CURRENT_REVISION` 상수가 `m_011`·`m_012` 추가 때 두 번 낡았다). 마이그레이션을 더 추가해도 깨지지 않고, "그래프에 head가 하나뿐"이라는 불변식이 별 테스트로 남아 있다. **상수로 되돌리지 말 것.**

### 3.3 백필은 없다 — 그리고 없어야 한다

네 컬럼 모두 `DEFAULT '{}'` / `1.0`이고 백필 스크립트가 없다. 빈 가중치를 도메인이 **균등**으로 읽으므로, 가중치 도입 전 리포트는 예전과 똑같은 단순 평균을 그대로 낸다.

**그게 그 리포트들이 실제로 채점된 방식이다.** 백필로 값을 채우면 역사를 다시 쓰는 것이 된다.

*(정정 2026-08-20: 이 절의 이전 판은 "계산기도 `scoring_inputs`가 빈 리포트에서는 아예 렌더되지 않는다"고 적었으나 사실이 아니다. `_scoring_breakdown_view`는 **항상** dict를 반환하고 `toScoreBreakdown`은 키 자체가 없을 때만 `null`을 낸다. 실제 렌더 차단 조건은 `ScoreCalculator`의 `contributions.length === 0`이다 — 즉 채점된 기준이 하나도 없을 때만 사라진다. 가중치 도입 전 리포트는 계산기가 **렌더되고**, 균등 가중치를 백분율로 보여준다(로컬에서 확인: `64점 × 100% / 합 64.0 ÷ 1.00`).*

*우려했던 `0 ÷ 0`은 나오지 않으므로 결함은 아니다. 다만 기준이 2개 이상인 옛 리포트는 기업이 설정하지 않은 `50% / 50%`를 설정된 것처럼 보여준다. 산술적으로는 그 리포트가 실제로 채점된 방식이지만 화면에 그 사실을 말하는 문구가 없다 — "이 리포트는 가중치 도입 전이라 균등 배분입니다" 같은 한 줄을 붙일지는 결정이 필요하다.)*

### 3.4 계약은 손으로 맞춘다 — 생성기가 없다

`scripts/generate_contracts.py`는 `7d977f7`에서 입력 스펙·의존성 3개와 함께 삭제됐다. `packages/contracts/openapi/`는 이제 **생성물이 아니라 손으로 관리하는 원본**이다.

응답에 필드를 더하는 것은 정해진 순서의 손 편집 3단계다:

1. `packages/contracts/openapi/root.yaml` — 계약
2. `packages/contracts/generated/typescript/openapi.d.ts` — SPA가 컴파일하는 대상(알파벳 순 유지)
3. 라우트 구현

`generated/python/`은 import하는 곳이 없어 갱신하지 않는다.

2번을 빠뜨리면 `npm run typecheck`가 잡는다. **1번을 빠뜨리면 원래 아무것도 잡지 않았다** — 그래서 리포트 응답에 한해 `test_report_view_contract.py`를 넣었다. 뷰가 내보내는 모든 키가 계약 스키마에 선언돼 있는지 확인하고, 스키마가 `additionalProperties: false`라 양방향으로 동작한다. (계약에서 `scoring_breakdown` 참조를 일시 제거해 실제로 실패하는 것을 확인했다.)

### 3.5 `zip(strict=False)` 처리

`runtime/worker.py`가 기준과 턴을 `strict=False`로 짝지어, 기준 수 > 답변 수면 **뒤쪽 기준이 조용히 사라졌다.** 가중치가 붙은 뒤에는 그게 분모를 몰래 줄이는 문제가 된다.

지금은 모든 기준이 리포트에 들어가고, 답변이 없는 기준은 `insufficient_evidence` 항목이 되어 **가중치가 보이는 상태로 제외**된다(`ReportGenerator._unscored_item`). `CriterionInput.answer_turn_id`/`transcript`가 `None` 허용인 이유가 이것이다 — 가짜 값을 채우지 않는다.

### 3.6 `null`은 절대 `0`이 아니다

세 곳에서 지킨다. 하나라도 0으로 바뀌면 **면접에서 묻지 않은 것 때문에 지원자가 떨어진다.**

- 축 점수 `null` → 분자·분모 양쪽에서 제외 (`scoring.aggregate`)
- 점수 없는 리포트 → `overall_score` 컬럼이 `NULL`
- 순위 표 → 점수 없으면 `"면접 전"`, 정렬 시 **맨 뒤**

---

## 4. 개발 환경에서 걸리는 것 (저장소 문제 아님)

Windows 워크스테이션에서 확인한 사항이다. Linux/CI에서는 해당하지 않는다.

| 증상 | 원인 / 우회 |
| --- | --- |
| `uv sync` / `uv run` 전부 실패 | 무언가가 자식 프로세스 출력에 `[0x...] ANOMALY: meaningless REX prefix used`를 주입해 uv의 인터프리터 질의 JSON을 깨뜨린다(3.13·3.14 동일, 주소 고정 → 주입된 DLL). 우회: `python -m venv .venv` 후 `pip install -e . --group dev`, 실행은 `.venv/Scripts/python.exe -m pytest` |
| `npm ci` EPERM | `esbuild.exe` 잠김. `npm install`을 쓴다. 단 그러면 `package-lock.json`에서 `"peer": true`가 지워지는 npm 버전 churn이 생기므로 **커밋 전에 `git checkout -- package-lock.json`** |
| `npm test` / `lint` / `typecheck` 실패 | Python 절반이 `UV_CACHE_DIR=... uv run ...`이라는 POSIX 환경변수 접두 문법이고 `cmd.exe`가 파싱하지 못한다. 두 절반을 따로 돌린다 |
| `prettier --check apps`가 100개 넘게 지적 | `core.autocrlf=true` + `.gitattributes` 없음 → 전 파일 CRLF, prettier 기본값은 LF. **`--write`로 전체를 고치지 말 것** — 무의미한 전 파일 diff가 된다. 자기가 편집한 파일만 |
| 타입 오류가 테스트에서 안 잡힘 | `apps/company-console/tsconfig.json`의 `"exclude": ["src/**/__tests__/**"]`. 필수 필드를 타입에 추가해도 픽스처는 `typecheck`를 통과한다 — 이번에 실제로 겪었고, 런타임에서 `—`로 드러났다. **조용히 틀린 값이 될 수도 있었다** |

---

## 5. 남은 일

### 5.1 C7 — 오너십 표시: Track 4와 함께

명세 6장이 요구하는 작업이고, **이번에 하지 않았다.** 이유와 조사 결과를 남긴다.

Track 4 머리말이 *"오너십 결과를 화면에 보여주는 일은 Track 2(6장)로 넘겼다. 이 트랙은 값을 채우는 데까지만 책임진다"*고 적었고, 명세 6장은 *"Track 4가 `candidate_identity_inputs`를 채우기 전까지는 전부 `CONTEXT_ONLY`"*라고 적었다. **두 문서가 서로를 가리키고 있다.**

**조사 결과 — 데이터가 화면 근처까지 오지 않는다.** 다시 조사하지 않도록 구멍을 적어 둔다.

| 계층 | `ownership_confidence` (float) | `ownership_class` |
| --- | --- | --- |
| `git_commit_analyses` 테이블 | 있음 | **있음** (여기가 끝) |
| 검색 인덱스 `retrieval_documents` | 있음 | 없음 |
| 검색 결과 → 경계 → Lane C | 있음 | 없음 |
| `question_source_references` 테이블 | 있음 | 없음 |
| Lane D 타임라인 투영 | 없음 | 없음 |
| 프론트 `ReviewQuestionSource` | 없음 | 없음 |

즉 질문 근거에 오너십을 붙이려면 **마이그레이션 2개**(`retrieval_documents`, `question_source_references`)와 약 10개 파일이 필요하다.

**그리고 `resolve_source_reference`(`submission_analysis/application/public.py`)는 프로덕션 코드에서 호출되지 않는다.** code unit → commit을 조회해 오너십 클래스를 꺼낼 수 있는 유일한 지점인데 호출처가 테스트뿐이다. 실제 질문 생성 경로는 검색 인덱스를 통과하고 인덱스에는 클래스가 없다. **`weight`가 저장만 되고 읽히지 않던 것과 같은 패턴이 하나 더 있는 셈이다.**

**Track 4와 함께 해야 하는 이유:**

1. Track 4 §1.2가 짚은 구멍은 **한 줄**이다 — `apps/applicant-interview/src/app/routeAdapters.tsx`의 `candidate_identity_inputs: {}`. 빈 dict라서 모든 커밋이 `CONTEXT_ONLY`로 분류된다.
   *(Track 4 문서는 이 줄을 `:213`으로 적었으나 `origin/develop` 기준으로는 **`:256`**이다. 줄번호로 찾지 말고 문자열로 grep할 것 — 이 파일은 자주 움직인다.)*
2. 그래서 지금 배관을 만들면 `PRIMARY_OWNED`가 제대로 렌더되는지 **테스트할 수 없다** — 그 값을 만들어 내는 코드가 없다. 화면에는 상수 하나만 나온다.
3. 이 트랙의 완료 기준 16개에 오너십 항목은 없다.

**Track 4 착수 시 순서:** 한 줄을 채우고 contributor 조회를 붙여 값이 실제로 생기게 한 뒤, 위 표의 구멍 3곳을 메우고 화면에 붙인다. 그때는 실제 값으로 검증할 수 있다.

> 참고: 그 한 줄은 표시 문제보다 크다. `HybridRetriever`의 `ownership_weight = 0.15`가 항상 0으로 곱해지므로 **검색 순위의 15%가 죽어 있다.** "지원자가 실제로 쓴 코드"에 가중치를 주려던 설계가 작동하지 않고, 질문이 남의 코드를 근거로 삼을 수 있다.

### 5.2 별건으로 남긴 것

명세 7장에 귀속과 함께 적혀 있다.

| 항목 | 상태 |
| --- | --- |
| 기준선(`passing_band`) 기업별 설정 | 후속. Level 3(LLM 입력)을 바꾸므로 회귀 세트 검증이 필요하다 (명세 2.4) |
| 기업이 쓴 `strong/weak_answer_signals`를 채점 프롬프트에 연결 | 후속 **최우선**. 지금 저장·검증·API 노출만 되고 **읽는 코드가 없다** (명세 7.2) |
| 지원자 고지·이의 제기 안내 | Lane A. 고지 문구가 `DEFAULT_CONSENT_POLICY` 도메인 상수여서 고치면 `policy_version`·`content_digest`가 바뀌고 진행 중인 동의가 무효화된다 (명세 7.1) |
| 축별 레이더 차트 / 점수 분산 신뢰도 | 별 작업 / 장기 |
| 기업 커스텀 축 | **폐기 확정.** 축 `guidance`가 채점 프롬프트에 그대로 렌더되므로 축을 열면 채점 기준 작성 권한을 기업에 넘기게 된다 (명세 2.1) |

### 5.3 이 트랙에서 고치지 않은 기존 결함

| 항목 | 비고 |
| --- | --- |
| `test_indexes_match_the_migrations` 실패 | ORM의 `ix_submissions_invitation_material`을 만드는 마이그레이션이 없다. Lane B 드리프트 |
| `backend/tests/{integration,contract}` 수집 오류 49건 | `7d977f7`이 인메모리 대역을 지웠다. `testpaths`가 `backend/tests/unit`만 가리키는 이유 |
| `generated/typescript`가 `openapi/`와 어긋남 | 다른 작업자가 `root.yaml`에 스키마 2개(`InterviewerPersonaDefinition`, `ApplicantInvitationPreview`)를 추가했으나 생성 타입을 갱신하지 않았다. 프론트가 그 필드를 쓰지 않아 typecheck는 통과한다 |

---

## 6. 병합 후 확인 순서

```bash
# 백엔드 — uv가 안 되면 4장의 우회를 쓴다
.venv/Scripts/python.exe -m pytest -q                       # 160 통과 기대
.venv/Scripts/python.exe -m mypy backend/src
.venv/Scripts/python.exe -m ruff check backend
.venv/Scripts/python.exe scripts/check_module_boundaries.py
.venv/Scripts/python.exe -m pytest -q backend/tests/integration/migrations/   # 10/1, head 1개

# 프론트
npm run typecheck --workspaces --if-present
npm run test --workspaces --if-present                      # 81 / 16 통과 기대
npm run build --workspaces --if-present
```

**숫자로 확인하는 것 3가지** — 병합이 산술을 건드리지 않았는지 가장 빨리 아는 방법이다.

1. `test_weighted_scoring.py::test_the_spec_example_reproduces_exactly` — `55.7 ÷ 0.75 = 74`
2. `test_weighted_scoring.py::test_changing_a_weight_cannot_change_a_stored_report` — 가중치를 뒤집은 새 리포트는 50, 저장된 리포트는 80 유지
3. `reportScoring.test.tsx::weights the axis averages by criterion ...` — `0.9×90 + 0.1×10 = 82` (단순 평균이면 50)

---

## 7. 목 데이터 — 고정 5축으로 다시 썼다

`apps/company-console/public/mock-data/recruiting.json`은 축이 5개로 고정되기 전에 작성돼서 `context` / `judgement` / `outcome` / `definition` / `learning` 같은 **백엔드가 만들 수 없는 축 키**를 쓰고 있었고, 가중치 필드가 하나도 없었다. 그래서 `VITE_USE_MOCK_DATA=true`로 백엔드 없이 콘솔을 열면 순위 열이 전부 "면접 전"이고 계산기에 넣을 데이터가 없었다.

다시 쓴 내용:

- `axisAssessments`가 `ASSESSMENT_AXIS_KEYS` 5개와 그 한국어 라벨을 쓰고, 축마다 `weight`를 갖는다
- `criterionVersions[*].axisWeights` — 포지션별로 다른 배분(백엔드 30/30/15/15/10, 제품 25/20/10/20/25)
- 리포트 항목마다 `criterionWeight`·`axisBreakdown`, 리포트마다 `scoringBreakdown`
- `invitations[*]`의 `overallScore` / `scoredCriteriaCount` / `totalCriteriaCount`

**점수는 손으로 적지 않았다.** `reporting/domain/scoring.py::aggregate`와 같은 산술로 계산해 넣었다 — 픽스처가 스스로 모순되면 읽는 사람이 어느 쪽을 믿을지 알 수 없다. 결과:

| 세션 | 종합 | 분자 ÷ 분모 | 보여주는 것 |
| --- | --- | --- | --- |
| `mock-session-001` | 87 | 86.90 ÷ 1.00 | 축 하나(깊이 30%)가 빠진 기준의 축 계산기 |
| `mock-session-002` | 72 | **46.80 ÷ 0.65** | 기준 하나(35%)가 제외된 **종합 분모 축소** |
| `mock-session-006` | 89 | 89.00 ÷ 1.00 | 5축 모두 채점된 정상 케이스 |

**남은 구멍: `/review/:sessionId`는 목을 타지 않는다.** `routeAdapters.tsx`의 `ReviewRoute`가 조건 없이 `companyRequest`로 실제 백엔드를 호출한다(다른 API는 전부 목 분기가 있다). 따라서 **계산기 화면은 목 모드로 볼 수 없고** 백엔드가 필요하다. 위 픽스처의 `scoringBreakdown`은 `ApplicantDetail` 경로와, 누군가 그 목 분기를 추가할 때를 위해 채워 뒀다. 분기를 넣는 것은 이 트랙에서 하지 않았다 — 검증 수단이 아니라 별건의 개발 편의 작업이다.

---

## 8. 로컬 스택에서 드러난 결함 3건 — 전부 수정했다

단위 테스트 206개, mypy, vitest, build가 모두 초록인 상태에서 실제 DB·API·브라우저로 열자 나온 것들이다. **세 건 모두 "조용히 틀린 값"이 아니라 500/422였고, 그래서 화면을 한 번도 열지 않으면 발견되지 않는다.**

### 8.1 저장된 평가기준 버전을 읽을 수 없었다 (HTTP 500)

`CompetencyModelVersion.criterion_weights_total_100`이 pydantic `field_validator`였다. validator는 **모든 구성 시점**에 돌고, `repositories/postgres.py`의 `_criterion_versions_from_rows`가 행을 읽을 때도 이 클래스를 구성한다. 규칙이 생기기 전에 저장된 버전은 총합이 100이 아니므로(위저드가 `합계 {totalWeight}`를 표시만 하고 검증하지 않았다) **모든 읽기 경로가 예외를 던졌다**: 평가기준 목록, 지원자 접근·동의, 채용 워크스페이스, 질문 생성, 면접 진행, 리포트 생성. `criteria_service.create_version`이 기존 버전 목록을 먼저 읽으므로 **새 버전 생성으로 우회할 수도 없었다.**

**수정:** validator에서 떼어 `create()`가 호출하는 classmethod로 옮겼다. 입력에는 엄격하고 재구성에는 관용이다. `criteria`는 생성 후 교체되지 않으므로(`publish`·`replace_persona`만 변경) 한 번 검사로 버전의 생애 전체가 보장된다. 명세 §2.3이 원한 것도 "게시 요청이 400으로 떨어지는 것"이다.

**데이터는 고치지 않았다.** `scoring.aggregate`가 총합으로 나누므로 30/25/20으로 저장된 버전은 **이미 40%/33%/27%로 채점된다** — 담당자가 설정한 비율 그대로다. 정규화 마이그레이션을 한 번 썼다가 철회했고, 이유는 두 가지다: 데이터를 고칠 필요가 없었고, `test_orm_declares_every_migrated_table`이 ORM에 없는 마이그레이션 전용 테이블(원본 보존용 백업 테이블)을 금지한다.

`CompetencyModelVersionView`가 `CompetencyModelVersionCreate`를 상속해서 **요청 규칙이 응답에도 걸리는** 같은 문제가 한 겹 더 있었다. 뷰에서 그 validator를 no-op으로 오버라이드했다.

### 8.2 채점축 가중치가 API로 저장될 수 없었다 (HTTP 422)

콘솔은 `axis_weights`를 POST하고(`routeAdapters.tsx`), 계약(`root.yaml`)과 생성 타입(`openapi.d.ts`)에도 선언돼 있었다. 그런데 라우트 요청 모델 `CompetencyModelVersionCreate`에 **그 필드가 없었고 `extra="forbid"`였다.** 실측 결과 `extra_forbidden loc=['body','axis_weights']` — **게시 요청 전체가 422로 떨어졌다.** `criteria_service.create_version`은 `axis_weights` 인자를 받는데 라우트가 넘기지 않았다. 배관이 라우트 한 층에서 끊겨 있었다.

`npm run typecheck`가 잡지 못한 이유는 요청 본문이 `body: JSON.stringify({...})`라서 객체 리터럴에 타입이 걸리지 않기 때문이다.

**수정:** 필드 추가 + 서비스로 전달 + `_criterion_view`가 되읽어 반환(없으면 위저드를 다시 열 때 슬라이더가 균등으로 초기화돼 기업이 그렇게 설정한 것처럼 보인다).

**재발 방지:** `test_criterion_version_contract.py`가 **계약이 선언한 속성이 요청·응답 모델에 다 있는지** 비교한다. 이것이 없던 검사다. 명세 §9.1이 "1번(계약)을 빠뜨리면 아무것도 잡지 않는다"고 적었는데, 실제로 일어난 것은 그 반대 방향이었다 — 계약과 프론트는 갱신됐고 라우트만 안 됐다.

### 8.3 시스템 기본 persona를 직렬화할 수 없었다 (HTTP 500) — `develop`의 기존 결함

`CompetencyModelVersion`이 `persona_definition`을 `{"mode": "system_managed", "tone": "neutral", "voice_id": "Seoyeon"}`로 기본 설정하는데, `InterviewerPersonaDefinitionInput`은 `name`을 요구하고 `neutral`을 tone으로 받지 않으며 `mode`를 extra로 거부한다. **persona 없이 게시된 모든 버전**이 응답 조립에서 예외를 던졌다.

이 트랙과 무관하게 `develop`에 이미 있던 결함이다(양쪽 정의 모두 `84af2d4`에 존재). 8.1을 고쳐도 같은 엔드포인트가 다른 이유로 500이어서 함께 고쳤다.

**수정:** `_persona_view()`가 담당자 정의 persona가 아니면 `None`을 반환한다. 콘솔의 `toCompanyPersona`가 이미 같은 세 가지 이유로 `undefined`를 내고, 계약에서도 `persona_definition`은 필수가 아니다. 담당자 persona는 요청 모델이 검증하므로 응답에서 실패하는 것은 도메인 기본값뿐이다.

### 8.4 곁들여 고친 것

`detail=str(error)`가 pydantic `ValidationError`를 그대로 담아, 축 가중치를 잘못 넣은 담당자가 타입 태그·입력 덤프·문서 URL을 보게 됐다. `companyClient`가 `detail`을 그대로 콘솔에 넘기므로 `_domain_error_detail()`이 validator가 쓴 문장만 뽑는다 — `"axis weights must total 100, got 50"`.

### 8.5 왜 테스트가 놓쳤는가

| 이유 | 근거 |
| --- | --- |
| repository 왕복을 검증하는 테스트가 없다 | `backend/tests/integration`이 수집 오류 49건으로 `testpaths` 밖이다(명세 9.2). 단위 테스트는 유효한 총합으로 **새** 객체만 만든다 |
| Lane A HTTP 계약 테스트가 죽어 있다 | `contract/company_management/test_http_contract.py`가 수집 오류. 명세 9.2가 "HTTP 경로는 사람이 확인한다"로 남긴 자리다 |
| 요청 본문에 타입이 걸리지 않는다 | `JSON.stringify({...})`의 객체 리터럴 |
| 응답 모델에 검증이 없다 | `get_report`에 `response_model`이 없다(명세 3.5). 평가기준 쪽은 있었지만 요청 모델을 상속해서 반대로 과하게 걸렸다 |

---

## 9. 로컬에서 실제로 확인하는 절차

단위 테스트로는 8장의 세 건이 잡히지 않는다. 화면까지 한 번 열어봐야 한다. Bedrock·GCP를 부르지 않으므로 **과금 0**이다.

```bash
# 1. 컨테이너 + 스키마
cp .env.example .env          # STT_PROVIDER=disabled, TTS_PROVIDER=text_only 로 두면 GCP 자격증명이 필요 없다
docker compose up -d --wait
PYTHONPATH=backend/src .venv/Scripts/python.exe -m interview_evidence.runtime.local_infra
.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade heads   # m_014_report_scoring

# 2. API (GCP/Bedrock 미사용)
PYTHONPATH=backend/src .venv/Scripts/python.exe -m uvicorn interview_evidence.main:app --port 8080

# 3. 콘솔
cp apps/company-console/.env.example apps/company-console/.env.local
npm run dev --workspace @iep/company-console
```

`.env`의 `LOCAL_COMPANY_ACCESS_TOKEN`과 `apps/company-console/.env.local`의 `VITE_LOCAL_COMPANY_TOKEN`이 같아야 한다. Vite가 `/v1`을 8080으로 프록시하므로 `VITE_API_BASE_URL`은 필요 없다.

**확인할 것 4가지**

1. `GET /v1/positions/{id}/competency-model-versions` → 200. 500이면 8.1이나 8.3이 되살아났다
2. 채용 생성 3단계에서 채점축 슬라이더를 움직여 게시 → 201/200. 422 `extra_forbidden`이면 8.2다
3. 잘못된 축 가중치(부분 dict·오타 키·음수·합계≠100)로 게시 → **422**이고 detail이 한 문장이다
4. `/review/:sessionId`에서 계산기가 `분자 ÷ 분모 = 점수`와 제외 기준·이유를 렌더한다

리포트가 없는 새 DB에서 4번을 보려면 실제 면접(GCP STT/TTS + Bedrock, 과금)을 돌리거나, `ReportGenerator`/`scoring.aggregate`/`repository.save_report`를 그대로 호출하는 스크립트로 리포트 하나를 주입하면 된다. 후자는 LLM이 낸 축 점수만 픽스처이고 DB 왕복·API 직렬화·프론트 렌더는 전부 실제 경로다 — 이 트랙의 산술을 확인하는 데는 그쪽이 충실도 대비 비용이 낮다.

**숫자로 확인하는 것 3가지** — 병합이 산술을 건드렸는지 가장 빨리 아는 방법이다.

1. `test_weighted_scoring.py::test_the_spec_example_reproduces_exactly` — `55.7 ÷ 0.75 = 74`
2. `test_weighted_scoring.py::test_changing_a_weight_cannot_change_a_stored_report` — 가중치를 뒤집은 새 리포트는 50, 저장된 리포트는 80 유지
3. `reportScoring.test.tsx::weights the axis averages by criterion ...` — `0.9×90 + 0.1×10 = 82` (단순 평균이면 50)
