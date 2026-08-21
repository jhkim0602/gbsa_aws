# Track 2 — 점수 산술 + 검토 화면

**상태:** 착수 가능 — **단 9장의 선행 조건을 먼저 해결한 뒤**. 요구사항 원본은 `docs/scoring-system-proposal.md`이고, 그 문서에서 채택되지 않은 항목은 해당 문서 상단과 이 문서 7장에 정리돼 있다.

**목표:** LLM은 축별 점수만 만들고, 기준·종합 점수는 순수 산술로 계산한다. 기업 가중치를 실제로 적용하고, "왜 74점인지"를 분모까지 드러내며, 모든 점수가 3단계 안에 영상 구간으로 추적되게 한다.

**전제:** 채점의 역할 분담(`assessment_service.py` 모듈 docstring)은 유지한다 — "모델이 숫자를 정하고, Python은 그 숫자를 보여줘도 되는지 정한다." 우리가 고치는 것은 **그 다음 단계인 집계**다.

**다른 트랙과의 겹침:** 없음. 단 **한 레인만 만지는 작업은 아니다** — 가중치의 출처는 Lane A이고 소비처는 Lane D다:

| 레인 / 앱 | 만지는 것 |
| --- | --- |
| Lane A `company_management/` | `domain/criteria.py`(`axis_weights` + 합계 검증), `application/company_service.py`(`CriterionVersionSnapshot`) |
| Lane D `reporting/` | `domain/report.py`, `domain/scoring.py`(신규), `repositories/postgres.py`, `api/company_routes.py`, `workers/reporting/report.py`, `runtime/worker.py` |
| company-console | `features/hiring/`(설정 UI·용어), `features/review/`(계산기), `features/company/`(비교 표) |
| Lane B `submission_analysis/` | **읽기만** — 6장의 오너십 표시. 쓰기 없음 |

경계는 기존 규칙을 그대로 지킨다: Lane D는 `CriterionVersionSnapshot`을 통해서만 가중치를 받고 Lane A의 `domain/`을 import하지 않는다(`scripts/check_module_boundaries.py`). 지원자 고지·동의 정책은 Lane A이지만 이 트랙 밖이다 — 7.1 참조.

---

## 0. 현재 상태 — `weight`는 저장만 되고 읽히지 않는다

`weight`는 4곳에 존재한다:

| 위치 | 내용 |
| --- | --- |
| `company_management/domain/criteria.py:83` | `weight: float = Field(ge=0)` |
| `company_management/application/company_service.py:55` | `CriterionSnapshot.weight: float` |
| `EvaluationDesigner.tsx:460/478` | range + number 입력 |
| `EvaluationDesigner.tsx:175` | `totalWeight` 계산 — `합계 {totalWeight}` 표시(`:377`)와 `CriterionOverview`(`:380`) 막대 스케일용으로만 쓰이고 **합계 검증 없음** |

**읽는 채점 코드가 하나도 없다.** 집계는 두 개의 단순 평균이다:

```python
# reporting/domain/report.py:138  ReportItem.average_score  (본문 :145-146)
scored = [axis.score for axis in self.axis_assessments if axis.score is not None]
return round(sum(scored) / len(scored)) if scored else None

# reporting/domain/report.py:189  Report.overall_score  (본문 :196-199)
scored = [item.average_score for item in self.scored_items if item.average_score is not None]
return round(sum(scored) / len(scored)) if scored else None
```

`scored_items`(`:185`)가 이미 `average_score is not None`으로 걸러 주므로 `overall_score`의 조건은 이중이다 — 가중평균으로 바꿀 때 이 두 곳이 같은 판정을 쓰게 유지한다.

`ASSESSMENT_AXES`(`reporting/application/assessment_prompt.py:65-111`)는 5개 고정 `Final` 튜플이고 `AssessmentAxis`에 **`weight` 필드가 없다** (`key` / `label` / `guidance`만).

**보존해야 할 판단** (`AxisAssessment` docstring, `report.py:96-98`): "`score`는 이 축을 판단할 근거가 없을 때 None이다. 절대 0이 아니다 — 0은 지원자가 틀렸다는 뜻이고, '물어보지 않았다'를 틀렸다고 처리하면 우리 면접의 공백으로 사람을 떨어뜨리게 된다."

---

## 1. 선행 작업 — 용어 충돌 해소

`EvaluationDesigner.tsx:368`이 `02 · 평가축`, `:575`가 `평가축 분포`. **여기서 "평가축"은 기업이 정의하는 *평가기준*(`EvaluationCriterion`)이다.** 그런데 LLM 채점의 5개 축(`ASSESSMENT_AXES`: 정확성·깊이·CS 기본기·본인 기여·설명력)도 "축"이다.

2단 가중치를 넣으면 설정 화면에 "축 가중치"가 두 종류 나타난다. 지금 이름으로는 해독 불가능하다. **가중치 작업 전에 반드시 정리한다:**

| 개념 | 코드 | UI 표기 |
| --- | --- | --- |
| 기업이 정의 (가변, 이름·설명·가중치 편집) | `EvaluationCriterion` | **평가기준** |
| LLM 채점 5개 (고정, 비중만 조절) | `AssessmentAxis` | **채점축** |

`EvaluationDesigner.tsx`에서 "평가축" → "평가기준"으로 바꾼다. 위 두 줄과 함께 각 카드 머리의 `축 {번호}` 라벨(`:388`)도 같이 바꿔야 한다 — **화면 문자열은** 이 세 곳이 전부다. 나머지 라벨(`:259`, `:325`, `:340`, `:404`, `:416`, `:496`, `:581`)은 이미 "평가기준"이다. `design.md:97`도 이미 "평가기준"이라 쓰고 있으므로 문서와 일치하게 된다.

### 1.1 식별자에도 같은 충돌이 있다

`EvaluationCriterion` 도메인 타입과 `criteria` 상태 필드는 올바르게 명명돼 있지만, **그 기준을 렌더하는 `EvaluationDesigner.tsx`의 스타일 상수는 전부 `AXIS_`로 시작한다.** 용어 충돌이 화면 문자열보다 식별자에 더 깊게 박혀 있다:

```
AXIS_LIST(:100)  AXIS_ITEM(:102)  AXIS_HEADER(:106)  AXIS_INDEX(:107)
AXIS_DELETE(:109)  AXIS_REQUIRED(:110)  AXIS_IDENTITY(:112)
AXIS_IDENTITY_INPUT_BASE(:121)  axisIdentityInputClass(:125)
AXIS_WEIGHT(:130)  AXIS_WEIGHT_LABEL(:132)  AXIS_WEIGHT_LABEL_TEXT(:133)
AXIS_WEIGHT_RANGE(:135)  AXIS_WEIGHT_INPUT(:137)
```

Tailwind 이관 전 CSS 클래스명도 같다 — 주석에 남은 `.criterion-axis-item`(`:101`), `.criterion-axis__identity`(`:116`).

**특히 `AXIS_WEIGHT_*` 네 개는 기업 *기준* 가중치 입력(`:455-485`)의 스타일 이름이다.** 2장에서 진짜 채점축 가중치 UI를 만들면 그 컴포넌트가 정확히 같은 이름을 원하게 되고, 그때는 어느 `AXIS_WEIGHT`가 어느 계층인지 읽을 수 없다. 따라서 이 14개를 `CRITERION_*`로 바꾸는 것이 **2장의 선행 조건이다** — 순수 rename이라 diff는 크지만 위험은 없다.

경계는 그대로 유지한다: `assessment_prompt.py`의 `ASSESSMENT_AXES` / `AssessmentAxis` / `AxisScore`와 `report.py`의 `AxisAssessment`는 진짜 채점축이므로 **건드리지 않는다.** 이 트랙 이후 `axis`라는 식별자는 채점축만 뜻한다.

---

## 2. 축 가중치 — 5개 고정, 비중만 조절

### 2.1 왜 추가·삭제를 막는가

각 축의 `guidance`(최대 1200자)가 **LLM 프롬프트에 직접 들어간다** (`assessment_prompt.py`). validator(`assessment_prompt.py:213`)가 `{axis.key for axis in ASSESSMENT_AXES}`에 없는 키를 거부한다. 기업이 임의 축을 추가하면 그 축의 `guidance`를 기업이 써야 하고, 채점 품질이 통제 불가능해진다.

`AssessmentAxis`의 docstring이 이미 이유를 말한다: "축은 회사별이 아니라 고정이다. 축은 엔지니어링 답변을 *읽는 방식*을 기술하고, 회사가 무엇을 중시하는지는 *어떤 기준을 묻는가*에 있다."

**따라서: 축은 5개 고정. 기업은 비중만 조절한다.**

**결정 (2026-08-20): 제안서의 "기업 커스텀 축 최대 7개"(Phase 3)는 폐기했다.** 보류가 아니라 폐기다. 따라서 이 트랙은 축이 정확히 5개라는 것을 **전제로 삼아도 된다** — 2.3의 "5개 키 전부" 규칙, `axis_weights`를 고정 키 dict로 두는 것, 3.3이 축 정의가 아니라 가중치만 동결하는 것이 모두 그 전제에 기댄다. 나중에 뒤집으려면 2.2·2.3과 `scoring_inputs` 스키마를 다시 쓰고 마이그레이션을 한 번 더 해야 한다(집계 산술·계산기 UI·비교 표는 축 개수와 무관하므로 그대로 남는다).

직무별 차별화는 축이 아니라 **평가기준**으로 한다. `criteria: tuple[EvaluationCriterion, ...] = Field(min_length=1)`(`criteria.py:107`)에는 개수 상한이 없고, 기준마다 기업이 이름·설명(4000자)·가중치·판단 유보 기준·검증 가이드를 직접 쓴다. "테스트 습관을 보고 싶다"는 요구는 채점축을 늘리는 것이 아니라 그런 평가기준을 만드는 것으로 충족된다.

### 2.2 어디에 저장하는가

`AssessmentAxis`에 `weight`를 넣지 않는다 — 그것은 프롬프트 설정이고 `Final` 상수다. 기업별 값이므로 `CompetencyModelVersion`에 둔다:

```python
# company_management/domain/criteria.py
axis_weights: dict[str, float] = Field(default_factory=dict)
# key는 ASSESSMENT_AXES의 key. 빈 dict는 균등 가중(현행 동작)을 뜻한다.
```

빈 dict = 균등을 기본으로 두면 **기존 published 버전이 그대로 동작한다.** 마이그레이션으로 값을 채워 넣지 않는다.

`CriterionVersionSnapshot`(`company_service.py:71-86`)에 `axis_weights`를 추가해 integration 경계를 넘긴다.

### 2.3 검증

기준 가중치·축 가중치 둘 다 `Field(ge=0)`뿐이고 합계 제약이 없다. 합계 검증을 도메인에 넣는다:

- 합계 0은 거부한다 (전부 0이면 나눌 수 없다).
- 합계 100을 **강제하지 않는다.** 대신 정규화한다: `normalized = weight / sum(weights)`. 담당자가 30/25/20을 넣고 합계 75여도 의도대로 동작하는 것이 낫고, 100을 강제하면 기준 하나를 삭제할 때마다 나머지를 다시 맞춰야 한다.
- **정규화한 값을 UI에 보여준다.** `EvaluationDesigner.tsx:377`이 이미 `합계 {totalWeight}`를 표시하므로, 그 옆에 "→ 30% / 25% / ..." 환산값을 붙인다.

`axis_weights`는 `dict[str, float]`이라 위 세 가지로는 부족하다. dict는 기준 튜플과 달리 **키가 틀릴 수 있고 일부만 채워질 수 있다.** 두 경우 모두 예외 없이 통과하고 점수만 조용히 달라지므로 도메인에서 막는다:

- **알 수 없는 키는 거부한다.** `{"correctnes": 40}`(오타)은 어떤 축과도 매칭되지 않아 무시되고, 담당자는 정확성을 40%로 설정했다고 믿는다. `CompetencyModelVersion`에는 이미 같은 모양의 검증이 있다 — `requirements_reference_known_criteria`(`criteria.py:135-145`)가 존재하지 않는 criterion code를 거부한다. `axis_weights`도 `model_validator(mode="after")`로 `{axis.key for axis in ASSESSMENT_AXES}` 밖의 키를 거부한다. 채점 쪽 `_known_axis`(`assessment_prompt.py:210-215`)와 같은 규칙이 설정 쪽에도 생기는 것이다.

- **부분 dict는 거부한다 — 빈 dict가 아니면 5개 키를 모두 요구한다.** "빈 dict는 균등"만 정하면 `{"depth": 40, "correctness": 30}`의 뜻이 정의되지 않는다. 없는 키를 0으로 읽으면 나머지 세 축이 채점에서 사라지고, 1.0으로 읽으면 40과 1.0을 같은 축척에서 더하게 된다. **둘 다 틀린 점수를 내고 어느 쪽인지 화면에 나타나지 않는다.** 전부 아니면 전무로 두면 이 해석 문제가 없어지고, 설정 UI는 5개 슬라이더를 항상 함께 보여주면 된다(§2.2의 "빈 dict = 균등"은 마이그레이션 없이 기존 버전을 살리기 위한 것이지 부분 설정을 허용하려는 것이 아니다).

- **값의 하한을 dict 안에도 넣는다.** `dict[str, float]`에는 `Field(ge=0)`이 값에 걸리지 않는다. 음수 가중치는 "이 축을 잘하면 감점"이라는 뜻이 되어 5장 비교 표에서 순위를 뒤집는다. 정규화 전에 거부한다.

**검증 위치가 중요하다.** 이 세 가지는 집계 함수가 아니라 `CompetencyModelVersion`에 있어야 한다. `CompetencyModelVersion`은 `frozen=True`이고 게시 후에는 `PublishedVersionImmutableError`(`criteria.py:15`)로 잠기므로, 잘못된 dict는 **게시 시점에 영구히 굳는다.** 집계에서 잡으면 면접이 이미 끝난 뒤 리포트 생성이 실패하고, 그 시점에는 고칠 방법이 없다(§3.3이 `scoring_inputs`에 그 값을 그대로 동결한다). 게시 요청이 400으로 떨어지는 것이 옳다.

### 2.4 기준선(`passing_band`)은 이 트랙에서 건드리지 않는다

제안서는 "기준선 60점 고정 → 기업별 설정 가능(기본값 60)"을 요구한다. **여기서는 하지 않는다.** 이유는 범위가 아니라 계층이 다르기 때문이다.

`passing_band`는 이미 파라미터화돼 있다 — `AssessmentPromptTemplate.passing_band`(`assessment_prompt.py:284`, `Field(default=PASSING_BAND, ge=1, le=99)`)이고, `rendered_system_prompt()`가 `{passing_band}`를 시스템 프롬프트 규칙 4에 렌더한다. 즉 값을 바꾸는 것 자체는 한 줄이다.

문제는 **그 한 줄이 축 점수 자체를 바꾼다는 것이다.** 이 트랙의 전제는 "모델이 정한 숫자는 그대로 두고 그 다음 단계인 집계만 고친다"이다. `passing_band`는 Level 3(LLM 판단)의 입력이므로, 그것을 기업 설정으로 열면 같은 답변이 기업 설정에 따라 다른 축 점수를 받는다. 가중치 작업과 성질이 다르고, 검증 방법도 다르다 — 가중치는 산술이라 단위 테스트로 고정되지만, 기준선 변경의 효과는 회귀 세트(`tests/regression/evidence/`)로만 확인된다.

넣기로 결정한다면 함께 바뀌어야 하는 것:

- `ASSESSMENT_PROMPTS`가 `InterviewLevel`별 상수 매핑(`assessment_prompt.py:319-321`)이므로, 기업별 값을 받으려면 템플릿을 요청 시점에 조립하는 구조로 바꿔야 한다.
- `prompt_version`이 `f"assessment-prompt-v1-{level.value}"`(`:304`)로 고정돼 있다. 기업이 기준선을 바꾸면 그 버전 문자열에 기준선이 들어가야 한다 — 그러지 않으면 같은 `prompt_version`의 두 리포트가 다른 기준으로 채점된다.
- 3.3의 `scoring_inputs`에 `passing_band`도 동결해야 한다.

**결정 (2026-08-20):** 이 세 항목은 후속 단계로 분리한다(7장 표). 이 트랙의 완료 기준(8장)에는 포함하지 않는다.

---

## 3. 집계 — 순수 산술, LLM 개입 없음

### 3.1 계산 순서

```
축별 점수 (LLM, 0~100 또는 None)
  → 축 가중치 적용 가중평균         → 기준 점수 (ReportItem)
  → 기업 기준 가중치 적용 가중평균   → 종합 점수 (Report)
```

두 단계 모두 **None을 제외하고 분모를 다시 계산한다.**

```python
def weighted(values: dict[str, int | None], weights: dict[str, float]) -> tuple[int | None, float, float]:
    """가중합, 사용된 가중치 합, 전체 가중치 합을 함께 반환한다.

    분모를 함께 반환하는 것이 이 함수의 존재 이유다. 점수만 돌려주면
    호출부가 78이 58.5/0.75인지 78/1.0인지 구별할 수 없고,
    계산기(4장)를 만들 수 없다.
    """
```

### 3.2 왜 분모를 반드시 노출하는가

이것이 이 트랙의 핵심 설계 판단이다.

"근거 부족 → N/A"와 "고정 가중치 가중합"은 **분모를 드러내지 않으면 합성되지 않는다.** 기준 A(30%)가 채점 불가로 제외되면 남은 가중치 합은 0.70이다. 이때 종합 점수를 `가중합 / 0.70`으로 계산하는데, 화면에 "78점"만 있으면 담당자는 그것이 100% 중 78인지 70% 중 78인지 알 수 없다. **추적성을 만들려는 작업이 추적성을 깨뜨린다.**

따라서 계산기는 항상 이 형태로 렌더한다:

```
기준 A  85점 × 30%  = 25.5
기준 B  72점 × 25%  = 18.0
기준 C  61점 × 20%  = 12.2
─────────────────────────
       55.7 ÷ 0.75 = 74점

제외됨
기준 D (25%) — 근거 부족: 이 기준에 해당하는 질문이 시간 내에 나오지 않았습니다
```

제외 항목과 **그 이유**를 반드시 함께 보여준다. 이유는 이미 있다 — `ReportItem.uncertainty`와 `assessment_state`(`INSUFFICIENT_EVIDENCE` / `NEEDS_FOLLOW_UP`).

### 3.3 계산 입력을 리포트에 동결한다

`Report`는 이미 `version` / `model_version` / `prompt_version` / `config_version` / `kind: AI_ORIGINAL`을 갖고 있고, `kind is not AI_ORIGINAL`이면 생성을 거부한다(`report.py:204-205`). 같은 원칙을 산술에 적용한다:

`ReportRow`(`reporting/repositories/postgres.py:175`)에 컬럼 추가:

```
scoring_inputs JSON NOT NULL DEFAULT '{}'
```

`{"axis_weights": {...}, "criterion_weights": {...}, "excluded": [{"criterion_id":..., "weight":..., "reason":...}], "numerator": 55.7, "denominator": 0.75}`

**기업이 나중에 가중치를 바꿔도 과거 리포트의 점수와 공식이 변하지 않는다.** `axis_assessments`가 이미 같은 이유로 JSON 배열로 저장된다(`postgres.py:221-223` 주석: "리포트와 함께 읽고 쓰며 리포트를 가로질러 조회되지 않으므로 자식 테이블이 아니라 JSON 배열 하나로 저장한다").

**마이그레이션은 `reporting/`이 아니라 `integration/`에 놓는다.**

```
backend/alembic/versions/integration/i_013_report_scoring_inputs.py
    revision      = "m_013_report_scoring_inputs"   # 27자
    down_revision = "m_012_position_interview"       # 현재 단일 head
```

`reporting/d_00N`으로 두면 안 된다. `d_001_reporting`은 `down_revision=None` / `branch_labels=("reporting",)`인 **레인 브랜치 루트**이고, 네 레인은 이미 `merge_001_lane_heads`에서 합쳐졌다. 그 뒤의 모든 마이그레이션은 `integration/`의 단일 선형 체인(`m_002` → … → `m_012_position_interview`)에 붙는다. `d_001` 뒤에 새 리비전을 달면 **이미 병합된 브랜치에서 두 번째 head가 갈라져** 다시 합쳐지지 않는다.

선례가 정확히 있다 — `integration/i_010_report_item_axis_scores.py`(`revision = "m_010_report_item_axis_scores"`)가 바로 이 작업의 쌍둥이다. Lane D 테이블(`report_items`)에 JSON 컬럼을 추가하면서 `integration/`에 `m_` 접두사로 들어갔다. 파일명은 `i_`, 리비전 id는 `m_`이라는 관례도 그 파일이 보여준다.

**리비전 id는 32자를 넘길 수 없다.** `alembic_version.version_num`이 `varchar(32)`이고 sqlite는 초과를 조용히 받아들이므로 테스트를 전부 통과한 뒤 첫 실제 Postgres upgrade에서 실패한다. `scripts/check_migrations.py`의 `MAX_REVISION_ID_LENGTH`와 `tests/integration/migrations/test_revision_ids.py`가 이것을 강제한다.

컬럼은 `NOT NULL DEFAULT '{}'`로 둔다 — `m_010`이 `axis_assessments`에 대해 같은 선택을 한 이유와 같다. 이 마이그레이션 이전에 생성된 리포트가 유효한 행으로 남아야 하고, 콘솔은 빈 객체를 "이 리포트에는 산술 내역이 없다"로 읽는다(가중치 도입 전 리포트의 점수는 단순 평균이며, 그것이 그 리포트가 실제로 계산된 방식이다). `tests/integration/migrations/test_orm_matches_migrations.py`가 `ReportRow`와 스키마 일치를 검사하므로 ORM 쪽 컬럼 추가를 빠뜨리면 잡힌다.

### 3.4 계산은 어디서 하는가

`Report.overall_score` / `ReportItem.average_score`를 property로 유지하되, **가중치를 인자로 받는 순수 함수로 계산을 옮긴다.** property는 `scoring_inputs`에 동결된 값을 읽어 재현한다. `reporting/domain/scoring.py`(신규)에 계산 함수만 둔다 — 도메인이므로 다른 레인에서 import되지 않는다(`check_module_boundaries.py`의 `PRIVATE_PACKAGES`에 `domain` 포함).

`ReportGenerator.generate`(`workers/reporting/report.py:68`)가 `axis_weights`와 `criterion_weights`를 받아 `Report`에 동결한다. 호출부는 `runtime/worker.py:244-254` `ReportRequestedEventHandler`(클래스는 `:182`) — 이미 `:204`에서 `self._company.get_criterion_version(...)`으로 `CriterionVersionSnapshot`을 받고 있으므로 `criterion.criteria[i].weight`와 `criterion.axis_weights`를 그대로 넘길 수 있다. **새 조회가 필요 없다.**

`CriterionInput`(`workers/reporting/report.py:38`)에 `weight: float = 1.0`을 추가한다. `runtime/worker.py:227-239`의 생성부에서 `weight=criterion_item.weight`. 그 생성부는 `zip(criterion.criteria, turns, strict=False)`로 기준과 턴을 짝지으므로 **기준 수와 턴 수가 다르면 뒤쪽 기준이 조용히 빠진다** — 가중치를 넘길 때 이 짝짓기가 곧 분모의 입력이라는 점에 유의한다.

### 3.5 API 응답

`reporting/api/company_routes.py:90` `_report_view`에 추가:

```python
"overall_score": report.overall_score,
"unscored_criteria_count": ...,          # 유지
"scoring_breakdown": {                    # 신규
    "criteria": [{"criterion_id":..., "criterion_name":..., "score":...,
                  "weight":..., "normalized_weight":..., "contribution":...}],
    "excluded": [{"criterion_id":..., "criterion_name":..., "normalized_weight":...,
                  "assessment_state":..., "reason":...}],
    "numerator": 55.7, "denominator": 0.75,
},
```

기준별 항목에도 `weight`와 축별 `weight`를 넣는다. `types.ts`의 `ReviewReport` / `ReviewReportItem` / `AxisAssessment`를 대응해서 확장한다.

**계약 파일도 같은 커밋에서 갱신한다 — 이것을 잡아 주는 테스트가 없다.**

`get_report`(`company_routes.py:210-231`)에는 `response_model`이 없고 반환형이 `dict[str, object]`다. 그래서 응답에 키를 추가해도 어떤 테스트도 실패하지 않는다. Lane D 계약 테스트(`backend/tests/contract/reporting/test_http_contract.py`)는 `app.openapi()`의 경로와 `operation_id`만 확인하고 응답 스키마는 보지 않는다.

즉 잊으면 이렇게 된다: `scoring_breakdown`이 API로 나가고, `packages/contracts/openapi/paths/reporting/paths.yaml`은 그대로 남고, 생성 타입 `packages/contracts/generated/typescript/openapi.d.ts`에는 그 필드가 없고, 프론트는 손으로 쓴 `features/review/types.ts`만 믿게 된다. **`weight`가 저장만 되고 읽히지 않았던 것과 같은 종류의 조용한 드리프트다** — 0장이 다루는 바로 그 문제.

따라서 이 순서를 지킨다:

1. `packages/contracts/openapi/paths/reporting/paths.yaml`(및 `root.yaml`의 `components/schemas`)에 `scoring_breakdown` 스키마를 먼저 쓴다.
2. `packages/contracts/generated/typescript/openapi.d.ts`를 **손으로** 같은 모양으로 맞춘다 — 생성기는 없다(9.1). `generated/python/`은 소비처가 없으므로 건드리지 않는다.
3. `_report_view`가 그 스키마와 같은 모양을 반환하게 한다.
4. `features/review/types.ts`와 `routeAdapters.tsx:658-670` 매핑을 맞춘다.

2번을 빠뜨리면 `npm run typecheck`가 잡는다. **1번을 빠뜨리면 아무것도 잡지 않는다.**

`unscored_criteria_count`의 기존 주석("82를 읽는 검토자가 세 기준이 채점되지 않았다는 것도 같이 보게 하기 위해")이 이 필드가 왜 계약에 있어야 하는지 이미 말하고 있다. `scoring_breakdown`은 같은 목적의 확장이므로 같은 대우를 받아야 한다.

---

## 4. 검토 화면 재편

### 4.1 현재 레이아웃

`features/review/ReviewWorkspace.tsx:36-46` (`WORKSPACE_LAYOUT`):

```
grid-cols-[minmax(280px,0.6fr)_minmax(0,830px)]
[grid-template-areas:'timeline report' 'decision report']
  1180px → 'timeline report' / 'decision decision'
   820px → 단일 컬럼
```

- `TimelineView` (363줄) — `playbackUrl`, `selectedStartMs`, `onSeek`
- `ReportView` (896줄) — 탭 구조 이미 있음: `OverviewPage`(299) / `CriteriaPage`(417) / `FollowUpPage`(736)
- `HumanReview` (238줄)
- 연결: `ReviewWorkspace.tsx:65`의 `const [selectedStartMs, setSelectedStartMs] = useState<number|null>(null)` 하나가 타임라인과 리포트를 잇는다. `ReportView.onSelectEvidence` → `setSelectedStartMs` → `TimelineView.selectedStartMs`(`:113`).

**영상↔리포트 연결 뼈대는 이미 있다.** 새로 만드는 것이 아니라 그 위에 계산기와 비교 뷰를 얹는다.

### 4.2 2단 구조

와이어프레임의 두 화면에 대응:

**① 지원자 개요** — 서류와 면접 요약을 한 화면에서 훑는다.

**이 화면은 이미 있다. 새로 만들지 않는다.** `/positions/:positionId/applicants/:invitationId`(`design.md:61`)는 `features/company/ApplicantDetail.tsx`(873줄)가 렌더하고, 이미 "지원자 종합 리포트" 제목 아래 탭 4개(제출 자료 / 분석 리포트 / …)와 처리 현황 메트릭, 그리고 `/review/:sessionId`로 가는 "검토 화면 연결" 링크(`:354-359`)를 갖고 있다.

이 트랙이 여기서 하는 일은 **종합 점수와 채점된 기준 수를 그 메트릭 영역에 추가하는 것 하나**다. 탭 구조·레이아웃·라우트는 건드리지 않는다. 6장의 오너십 표시도 기존 "제출 자료" 탭 안에 붙인다.

**② 상세 리포트** — `/review/:sessionId`. 현재 화면을 유지하되:
- 좌측 재생기 + 타임라인 (`TimelineView` — 이미 질문/답변/이벤트 엔트리를 모두 렌더)
- 우측 탭: **AI 리포트 / 계산기 / 후속 확인** — `ReportView`의 기존 3탭 구조를 재사용한다. `OverviewPage`에 계산기를 넣는다.

레이아웃 그리드는 **바꾸지 않는다.** `ReviewWorkspace.tsx:17-46`의 주석들이 Tailwind 이관 때 계산한 CSS 우선순위 결과를 기록해 두고 있어(`.review-page-meta > span` (0,1,1) vs `.status-badge` (0,1,0), `.page-eyebrow`가 `.page-header p`에 색·크기·마진을 잃는 것 등) 재작성하면 그 지식이 사라진다. 탭 내용만 추가한다.

### 4.3 계산기 컴포넌트

`ReportView.tsx`의 `OverviewPage`(299줄)에 들어간다. 이미 `report.overallScore`를 34px로 크게 렌더하고(`:308-313`) `toneOf()`로 색을 정하며, null이면 `—`를 쓴다. 보조 문구(`:315-318`)가 "기준 N개 평균"까지 이미 말하고 있으니 그 자리가 분모를 붙일 곳이다. 그 아래에 3.2의 표를 붙인다.

`ScoreValue`(796) / `ScoreBar`(812) / `summarizeAxes`(839)가 이미 있으므로 재사용한다. `ScoreValue`의 주석("An unjudged axis is greyed and set smaller: it must never read as a zero.")이 0장의 원칙을 프론트에서 이미 지키고 있다 — 계산기의 새 숫자도 같은 규칙을 따른다. `summarizeAxes`는 축별 평균을 내는데 **가중치를 반영하도록 고친다** — 여기가 화면에서 가중치가 처음 보이는 곳이다.

### 4.4 3단계 추적 보장

요구: 종합 점수 → 기준·축 점수 → Evidence → 영상 구간.

**이 체인은 이미 구현돼 있고 테스트도 있다.** `features/review/__tests__/evidenceTraceability.test.tsx`가 9개 케이스로 이것을 고정한다 — 축 점수가 개수 대신 실제 Evidence에 닿는지, 인용이 트랜스크립트의 지원자 발언으로 풀리는지, 검토자가 인용을 따라갔을 때 영상이 seek되는지, 그리고 정직하게 불완전한 두 경우(트랜스크립트에 없는 답변, Evidence 행이 더 이상 들고 있지 않은 인용)까지. 파일 상단 주석이 그 의도를 적어 두었다: "검토자는 어떤 숫자 뒤의 답변에든 한 화면에서 닿을 수 있어야 한다."

서버 측 보장도 이미 있다:

- `AxisAssessment.quoted_evidence_ids`는 서버가 검증한다 — `assessment_service.py:109`의 `verdict.verified_against(frozenset(answer.evidence_id ...))`가 실재하지 않는 Evidence를 인용한 축의 점수를 죽인다. **이 검증을 유지한다.**
- `Evidence`는 `video_start_ms` / `video_end_ms` / `transcript_segment_id`를 갖고 있다(`_report_view`가 이미 내려준다).
- 조립은 클라이언트에서 한다. `types.ts:108-112`의 `ReviewEvidenceContext`를 `buildEvidenceContext(timeline.entries)`(`ReviewWorkspace.tsx:67`)가 만든다. **이 위치를 이 트랙에서 서버로 옮기지 않는다** — 옮기면 타임라인 API 계약과 위 9개 테스트가 함께 바뀌고, 그건 가중치 작업과 무관한 diff다.

**따라서 이 절의 작업은 "새 테스트를 만드는 것"이 아니라 기존 테스트를 확장하는 것이다:** 계산기(4.3)에 붙는 새 숫자들 — 기준별 `contribution`, 제외 항목 — 도 같은 방식으로 Evidence에 닿는지, 그리고 제외된 기준은 닿을 Evidence가 없다는 것이 화면에 이유와 함께 나오는지. `ReportView.tsx:438` `followEvidence(evidence)`가 이미 그 경로다.

### 4.5 사람의 판단은 AI와 섞이지 않는다

`Report`는 `kind is not AI_ORIGINAL`이면 생성을 거부한다(`report.py:204-205`) — 이 불변식을 유지한다. 사람의 수정은 `HumanReview`로만 기록되고, `ReviewWorkspace.tsx:71-80`의 `overrideAssessment`가 `reportItemId`·`assessmentState` 두 개만 받아 사유는 `"기업 검토자가 평가 상태를 수정함"`으로 고정해 넘긴다.

**고정 사유를 자유 입력으로 바꾼다.** 요구사항이 "사유를 기록할 수 있음"인데 지금은 모든 override가 같은 문자열이라 기록의 의미가 없다. `api.overrideAssessment(reportItemId, assessmentState, reason)`는 이미 `reason`을 받으므로 **바뀌는 것은 UI와 그 사이 래퍼의 시그니처뿐이다** — `HumanReview`에 입력을 두고 래퍼에 `reason` 인자를 추가한다. `evidenceTraceability.test.tsx`가 `overrideAssessment`를 mock으로 갖고 있으므로 인자 검증을 거기에 붙일 수 있다.

---

## 5. 비교 대시보드

**순위 표는 `/applicants`가 아니라 `/positions/:positionId`에 둔다.**

`/applicants`(`features/company/ApplicantManagement.tsx`)는 **전체 포지션을 횡단하는** 목록이다 — 컬럼이 지원자 / 포지션 / 현재 상태 / 면접 결과(`:197-201`)이고, 화면 설명도 "전체 포지션의 지원자 진행 상태"(`:123`)다. 여기에 점수 열을 붙여 정렬하면, **서로 다른 평가기준 집합과 서로 다른 가중치로 산출된 숫자를 한 열에 세우게 된다.** 백엔드 시니어의 78과 프론트엔드 신입의 82는 비교 가능한 양이 아니다.

이것은 아래 세 번째 항목(분모가 다르면 비교가 아니다)의 더 강한 형태다. 분모가 다른 것은 표식으로 완화할 수 있지만, **기준 집합 자체가 다른 것은 표식으로 해결되지 않는다.** 그래서 순위 표는 포지션 안에서만 세운다:

- **`/positions/:positionId`**(`features/company/PositionOperations.tsx`)의 지원자 목록에 점수·채점된 기준 수·정렬을 추가한다. 이 포지션의 모든 지원자는 같은 `CompetencyModelVersion`으로 채점됐으므로 비교가 성립한다. 제안서 §7.1의 시나리오("포지션: 백엔드 시니어, 20명 지원")가 가리키는 화면도 이쪽이다.
- **`/applicants`에는 점수 열을 넣지 않는다.** 이 화면은 "누가 검토 대기 중인가"를 보는 진행 상태 목록으로 남긴다. 점수는 포지션 상세에서 본다.
- 정렬 가능한 표. `design.md:29-31`의 원칙("반복 업무와 비교가 중심인 조용한 운영 도구", "카드 중첩을 피하고 표 형태의 행")을 따른다.
- **순위가 결정이 아니라는 것을 화면이 말해야 한다.** `unscored_criteria_count`를 점수 옆에 항상 표시한다 — `_report_view`의 주석이 이미 그 이유를 적어 두었다: "82를 읽는 검토자가 세 기준이 채점되지 않았다는 것도 같이 보게 하기 위해."
- 채점 불가 기준이 서로 다른 두 지원자의 점수는 **같은 분모가 아니다.** 표에 분모를 병기하거나, 분모가 다른 행에 표식을 넣는다. 이것을 빼면 비교 대시보드가 잘못된 비교를 만든다.

---

## 6. 오너십 노출 (Track 4에서 넘어온 항목)

`classify_commit_ownership`(`submission_analysis/domain/git_analysis.py`)이 `PRIMARY_OWNED` / `SHARED` / `CONTEXT_ONLY`와 `explanation_codes`를 저장하는데 **담당자가 볼 화면이 없다.** 남의 코드로 만든 질문인지 사람이 판단할 수 있어야 한다.

- 개요 화면(4.2 ①)의 GitHub 항목에 오너십 분류와 `requires_verification`을 표시한다.
- 상세 리포트의 질문 근거(`ReviewQuestionSource`, `QuestionSources` 컴포넌트 `ReportView.tsx:701`)에 그 소스의 오너십을 붙인다.

Track 4가 `candidate_identity_inputs`를 채우기 전까지는 전부 `CONTEXT_ONLY`로 표시된다 — 그것이 정확한 표시다.

**상태 (2026-08-20): 이 절은 구현하지 않았고 Track 4와 함께 한다.** 조사해 보니 오너십 *클래스*가 `git_commit_analyses` 테이블에서 끊긴다 — 검색 인덱스, `question_source_references`, 타임라인 투영 세 곳에 없어서 마이그레이션 2개와 약 10개 파일이 필요하다. 게다가 그것을 꺼낼 수 있는 유일한 함수(`resolve_source_reference`)가 프로덕션에서 호출되지 않는다. 그리고 Track 4 §1.2의 한 줄이 채워지기 전에는 모든 값이 `context_only`라 `PRIMARY_OWNED`가 제대로 렌더되는지 검증할 방법이 없다. 구멍의 정확한 위치와 착수 순서는 `track-2-handover.md` 5.1에 있다.

---

## 7. 이 트랙이 다루지 않는 것

제안서(`docs/scoring-system-proposal.md`)에는 있으나 여기서 의도적으로 제외한 항목이다. **누락이 아니라 귀속의 문제이므로, 각 항목이 어디로 가는지 적어 둔다** — 그러지 않으면 "가중치 트랙이 끝났다"가 "제안서가 구현됐다"로 읽힌다.

| 제안서 항목 | 왜 여기가 아닌가 | 어디로 |
| --- | --- | --- |
| 기준선 기업별 설정 (§3.3) | Level 3(LLM 입력)을 바꾼다 — 2.4 참조 | 후속 단계 |
| 기업 커스텀 축 최대 7개 (Phase 3) | **폐기 확정 (2026-08-20).** 근거는 2.1 | 하지 않는다 |
| 기업이 쓴 `strong/weak_answer_signals`를 채점에 반영 | **제안서에 없는 항목이지만 여기 적어 둔다** — 아래 7.2 | 후속 단계 |
| 축별 레이더 차트 (Phase 2) | 4.3은 기존 `ScoreBar`(`:812`) 재사용까지만 한다. 새 차트 라이브러리는 두 SPA의 의존성 결정이다 | 별 작업 |
| 점수 분산·신뢰도 ±5점 (Phase 4) | 같은 답변을 재채점해야 하는데 리포트는 immutable이다. 구조가 다르다 | 장기 |
| 점수 산출 공식 사전 고지 (§9.2) | Lane A. 아래 참조 | Lane A 트랙 |
| AI 평가 이의 제기 안내 (§9.2) | Lane A. 아래 참조 | Lane A 트랙 |
| 기업별 점수 분포 편향 모니터링 (§9.2) | 리포트를 가로질러 집계해야 한다. 이 트랙은 리포트 하나 안의 산술만 만진다 | 별 트랙 |

### 7.1 지원자 고지 3항목은 Lane A이고, 값싸지 않다

제안서 §9.2의 세 항목 중 앞의 두 개는 지원자 동의 화면에 문구를 넣는 일로 보이지만, 그 문구는 UI 문자열이 아니라 **도메인 상수**다.

`DEFAULT_CONSENT_POLICY`(`company_management/domain/applicant_access.py:54-86`)가 `ai_role`, `recording_notice`, `processing_purposes[AI_ASSESSMENT].description`을 하드코딩하고 있고, 이미 관련 내용을 고지한다 — "AI는 지원자 자료를 바탕으로 질문과 평가 초안을 만들지만 최종 채용 결정은 기업의 사람이 수행합니다."

여기에 점수 공식을 추가하면 `policy_version`(`"2026-08-v1"`)과 `content_digest`(정책 전체의 SHA256, `:41-51`)가 바뀐다. 그리고 `applicant_access_service.py:83-84`가 **제출된 `policy_version`·`consent_content_digest`가 현재 정책과 다르면 동의를 거부한다.** 즉 문구 한 줄을 고치는 것이 진행 중인 지원자의 동의를 무효화한다.

따라서 이 두 항목은 정책 버전 전환 절차(구버전 동의를 어떻게 취급할지)와 함께 Lane A에서 다뤄야 한다. Lane D 작업에 끼워 넣을 수 없고, **이 트랙의 완료가 GDPR Article 22 대응을 뜻하지 않는다는 점을 분명히 한다.**

### 7.2 기업이 쓴 채점 신호가 채점 프롬프트에 도달하지 않는다

커스텀 축을 폐기하면서 "그럼 기업별 채점 관점은 어디로 가는가"가 남는다. **답은 이미 만들어져 있는데 연결이 안 돼 있다.**

`CriterionVerificationGuide`(`criteria.py:52-73`)에서 기업이 기준마다 작성하는 것:

| 필드 | 소비처 |
| --- | --- |
| `observable_dimensions` | 질문 생성·검색 색인 (`integration/company_analysis.py:50`, `submission_interview.py:235`) ✓ |
| `follow_up_directions` / `max_follow_ups` / `time_budget_seconds` | 면접 진행 정책 ✓ |
| **`strong_answer_signals`** | **없음** |
| **`weak_answer_signals`** | **없음** |
| **`abstain_guidance`** | **없음** (저장·API 노출만) |

뒤의 세 개는 도메인에 정의되고(각 최대 12개, 빈 문자열 금지), DB에 저장되고, API로 오가는데 **읽는 코드가 하나도 없다.** 채점 프롬프트가 받는 기준 정보는 `criterion_name`과 `criterion_text`(= `description`) 둘뿐이다(`assessment_service.py:79-80`). 기업이 "이 기준에서 이런 답변은 약하다"를 12개 써 넣어도 채점하는 모델은 그것을 보지 못한다.

**`weight`가 저장만 되고 읽히지 않았던 것과 정확히 같은 문제다** — 0장이 다루는 그 문제. 이것을 `build_assessment_prompt`의 payload에 연결하면 커스텀 축 없이도 기준 단위로 기업 관점이 반영되고, 축 구조를 전혀 건드리지 않는다.

**여기서 하지 않는 이유는 하나뿐이다:** 2.4의 `passing_band`와 같은 범주 — Level 3(LLM 입력)을 바꾸므로 회귀 세트로 검증해야 하고, 집계 트랙과 성질이 다르다. 다만 **기록해 두지 않으면 `weight`처럼 또 잠들 항목이므로** 후속 단계의 최우선으로 남긴다.

---

## 8. 완료 기준

1. `EvaluationDesigner.tsx`에서 기업 기준이 "평가기준"으로 표기되고 "평가축"이 남아 있지 않으며, 기준을 렌더하는 `AXIS_*` 스타일 상수 14개가 `CRITERION_*`로 바뀌었다(1.1).
2. `CompetencyModelVersion.axis_weights`가 존재하고, 빈 dict가 균등 가중으로 동작한다(기존 버전 무변경).
3. 가중치 합계 0은 거부되고, 그 외는 정규화되며, 정규화 결과가 설정 UI에 표시된다.
4. `axis_weights`가 알 수 없는 키·부분 dict(빈 dict 제외)·음수 값을 게시 시점에 거부하고, 그 거부가 집계가 아니라 `CompetencyModelVersion`에서 일어난다(2.3).
5. `Report.overall_score`(`report.py:189`)와 `ReportItem.average_score`(`:138`)가 가중평균이고, `score is None`이 분자·분모 양쪽에서 제외된다.
6. `reports.scoring_inputs` 컬럼이 있고 가중치·분자·분모·제외 목록이 동결된다. 기업이 가중치를 바꿔도 기존 리포트 점수가 변하지 않음을 테스트가 검증한다.
7. 마이그레이션이 `integration/i_013_report_scoring_inputs.py`이고 `down_revision`이 당시의 단일 head다. `alembic heads`가 여전히 하나를 보고한다(3.3).
8. `/report` 응답에 `scoring_breakdown`이 있고 `numerator` / `denominator`를 포함한다.
9. **`packages/contracts/openapi/`에 `scoring_breakdown` 스키마가 있고 `packages/contracts/generated/`가 그것으로부터 재생성됐다.** 응답과 계약이 어긋나도 실패하는 테스트가 없으므로 이 항목은 사람이 확인한다(3.5).
10. 계산기가 `55.7 ÷ 0.75 = 74` 형태로 분모를 렌더하고, 제외 항목과 이유를 함께 보여준다.
11. `evidenceTraceability.test.tsx`의 기존 9개 케이스가 그대로 통과하고, 계산기의 새 숫자(기준별 기여도·제외 항목)에 대한 케이스가 거기에 추가됐다.
12. `score is None`이 어디서도 0으로 렌더되지 않고 평균에 포함되지 않는다.
13. override 사유가 자유 입력이고 `HumanReview`에 저장된다.
14. `/positions/:positionId` 순위 표에 가중치 적용 점수 + 채점된 기준 수가 있고, `/applicants`에는 점수 열이 없다(5장).
15. `Report.kind is AI_ORIGINAL` 불변식이 유지된다.
16. `npm run typecheck` / `npm test` / `npm run build` 통과.

---

## 9. 선행 조건 — 착수 전에 처리한 것 *(완료, 2026-08-20)*

**증상:** `backend/tests/contract/test_generated_contract_drift.py::test_generated_contracts_are_current`가 `python scripts/generate_contracts.py --check`를 실행하고 종료 코드 0을 요구하는데, **그 스크립트가 없다.** 커밋 `7d977f7`("chore: remove legacy specification and test harness assets")에서 삭제됐다.

*(정정: 이 문서의 이전 판은 "따라서 `npm test`가 빨간 상태다"라고 적었으나 사실이 아니다. `testpaths`가 `backend/tests/unit`만 가리켜 `backend/tests/contract`는 애초에 실행되지 않았다 — 9.2 참조. 이 테스트는 명시적으로 파일을 지정해 돌릴 때만 실패했다. 삭제 이유는 여전히 유효하다: 존재하지 않는 스크립트를 호출하는 죽은 코드이고, 계약 갱신 절차를 잘못 안내한다.)*

**처음에는 "복구"를 지시했으나 그것이 틀렸다.** 그 커밋은 스크립트만 지운 것이 아니라 계약 생성 도구 전체를 지웠다:

| 지워진 것 | 정체 |
| --- | --- |
| `scripts/generate_contracts.py` (255줄) | 생성기 |
| `specs/001-interview-evidence-platform/contracts/openapi.yaml` (1992줄) | **생성기의 입력** |
| `datamodel-code-generator` (pyproject dev) | Python 모델 생성 |
| `openapi-typescript`, `json-schema-to-typescript` (package.json devDeps) | TS 선언 생성 |
| `packages/contracts/package.json`의 `generate` / `check` | 진입점 |

스크립트는 두 반쪽이었다. `build_openapi_files()`가 위의 레거시 스펙을 읽어 `packages/contracts/openapi/`로 **쪼개고**, `generate_types()`가 그 결과에서 `generated/`를 만들었다. `main()`이 `--check`에서도 `build_openapi_files()`를 먼저 호출하므로, 입력이 없으면 `--check`조차 죽는다.

즉 그 커밋의 의도는 명확하다 — **`packages/contracts/openapi/`를 생성물에서 손으로 관리하는 원본으로 바꾼 것이다.** 복구는 의존성 3개를 되살리고 1992줄 레거시 스펙을 다시 만드는 일이며, 그 결정을 되돌리는 것이다.

**따라서 한 것:** 고아가 된 테스트 함수만 삭제했다. 같은 파일의 `test_openapi_paths_have_exactly_one_owner_lane`은 건강하므로(4개 fragment에 `x-owner-lane` 45개 존재) 남겼고, 삭제 이유와 그 뒤에 남는 보장을 파일 docstring과 `packages/contracts/generated/README.md`에 기록했다. 후자는 존재하지 않는 `npm run contracts:generate`를 안내하고 있어 함께 고쳤다.

### 9.1 그래서 계약을 지키는 것은 무엇인가 — 3.5와 6장에 직접 영향

드리프트 검사가 없어진 뒤 남은 것:

- **`generated/typescript/openapi.d.ts`는 두 SPA가 실제로 import한다** — `companyClient.ts:1`, `company-console/routeAdapters.tsx:35`, `applicant-interview/routeAdapters.tsx:1`이 `@iep/contracts`를 통해 `components`를 가져온다. 프론트가 읽는 필드가 여기 없으면 `npm run typecheck`가 실패한다. **이것이 유일하게 남은 자동 검사이고, 프론트가 쓰는 필드만 커버한다.**
- **`generated/python/`은 import하는 곳이 하나도 없다.** 조용히 드리프트한다. 갱신 대상에서 제외한다.
- `get_report`에는 `response_model`이 없으므로(3.5) **응답과 `openapi/`가 어긋나도 실패하는 테스트가 없다.**

그래서 응답에 필드를 더하는 일은 **정해진 순서의 손 편집 3단계**다:

1. `packages/contracts/openapi/` — 계약. **아무것도 검증하지 않는다. 사람이 지켜야 한다.**
2. `generated/typescript/openapi.d.ts` — SPA가 컴파일하는 대상. 빠뜨리면 `typecheck`가 잡는다.
3. 라우트 구현.

1번을 건너뛰면 게시된 계약이 존재하지 않는 API를 설명하게 되고, 아무 테스트도 그것을 말해 주지 않는다. 완료 기준 9번이 이 항목을 "사람이 확인한다"로 둔 이유다.

### 9.2 무엇이 실제로 검증되는가 — 완료 기준 16번의 실체

`npm test`의 Python 절반은 **`backend/tests/unit`만 돌린다.** `pyproject.toml`의 `testpaths`가 그렇게 좁혀져 있고, 그 안에서도 `addopts`가 12개 파일을 `--ignore`한다. 이유는 주석에 적혀 있다 — `7d977f7`이 인메모리 대역(`InMemoryCompanyRepository`, `InMemoryAuditAppender`, `InMemoryOutbox`, `FakePrincipalProvider`, `DeterministicAIModel`, `create_local_runtime`, …)을 `backend/src`에서 지웠고, 그것을 import하는 테스트는 assert가 아니라 **수집 단계에서** 죽는다.

측정한 기준선 (2026-08-20, 이 트랙 착수 시점):

| 대상 | 결과 |
| --- | --- |
| `pytest` (= `testpaths`, `npm test`가 돌리는 것) | **131 통과, 0 실패** |
| `backend/tests/integration` | 37 수집, **44 수집 오류** |
| `backend/tests/contract` | 10 수집, **5 수집 오류** |
| `tests/` (e2e·regression·load) | 6 수집, **6 수집 오류** |
| `infra/tests` | 16 수집 — 정상이지만 `testpaths` 밖이라 `npm test`가 돌리지 않는다 |
| vitest (`company-console` / `applicant-interview`) | 13파일 59테스트 / 5파일 14테스트 **전부 통과** |
| `tsc -b` (두 SPA) | 통과 |
| `mypy backend/src` | 통과 (157 파일) |

**따라서 완료 기준 16번의 `npm test`는 "unit 131개 + vitest 73개가 통과한다"는 뜻이다.** 그 이상을 뜻하지 않는다.

이 트랙에 필요한 검증 중 **`testpaths` 밖이지만 명시 지정으로 돌아가는 것**(즉 쓸 수 있는 것):

| 파일 | 상태 | 이 트랙에서의 용도 |
| --- | --- | --- |
| `integration/migrations/test_revision_ids.py` | 3 통과 | 새 리비전 id의 32자 제한 |
| `integration/migrations/test_orm_matches_migrations.py` | 5 중 4 통과 | ORM ↔ 마이그레이션 컬럼 일치 |
| `integration/reporting/test_report_read_query_count.py` | 2 통과 | 가중치 추가가 쿼리 수를 늘리지 않음 |
| `integration/reporting/test_axis_assessment_persistence.py` | 3 통과 | 축 점수 JSON 왕복 |
| `unit/company_management/test_criterion_versioning.py` | 3 중 2 통과 (`--ignore` 목록에 있으나 명시 지정 시 수집됨) | `axis_weights` 검증 |

**쓸 수 없는 것** (수집 오류): `contract/company_management/test_http_contract.py`, `integration/cross_module/test_invitation_review_projection.py`. 앞의 것은 C2(Lane A 계약), 뒤의 것은 C6(초대 투영)에 쓰려던 것이므로 **그 두 단계는 새 단위 테스트로 커버하고, HTTP 경로는 사람이 확인한다.**

#### 착수 전에 이미 빨간 것 4개 — 내가 깬 것과 구별하기 위해 기록한다

1. `integration/migrations/test_lane_merge.py` (2개) — `CURRENT_REVISION`이 `"m_010_report_item_axis_scores"`로 박혀 있는데 실제 head는 `m_012_position_interview`다. `m_011`·`m_012`를 추가할 때 아무도 갱신하지 않았다. **이 트랙이 `m_013`·`m_014`를 추가하므로 이 상수를 함께 갱신한다** — 그 테스트가 head를 확인해 주는 유일한 장치다.
2. `integration/migrations/test_orm_matches_migrations.py::test_indexes_match_the_migrations` — ORM이 선언한 `ix_submissions_invitation_material`(`submissions`)을 만드는 마이그레이션이 없다. Lane B의 기존 드리프트이고 점수와 무관하다. **이 트랙에서 고치지 않으므로, 같은 파일의 컬럼 일치 테스트만 게이트로 쓴다.**
3. ~~`integration/migrations/test_cleanup_script_matches_the_schema.py` (2개)~~ — `scripts/cleanup_test_positions.sql`을 참조하는데 `7d977f7`이 지웠다. 계약 드리프트 테스트와 같은 종류의 고아여서 **함께 삭제했다.** 그 파일이 담고 있던 실패 이력(누락된 `session_checkpoints`, 분석보다 뒤에 놓인 `submission_chunks`)은 `docs/local-development.md`의 "No seed data" 절로 옮겼다 — 스크립트를 되살리면 테스트도 함께 되살려야 한다는 조건과 함께.
4. `unit/company_management/test_criterion_versioning.py::test_invitation_pins_the_published_criterion_version` — `Invitation.create()`를 `submission_requirements` 없이 호출한다. `pyproject.toml` 주석이 이미 원인을 적어 둔 항목이다.

#### Windows에서의 실행 방법

`npm test` / `npm run lint` / `npm run typecheck`의 Python 절반은 `UV_CACHE_DIR=... uv run ...`라는 **POSIX 환경변수 접두 문법**이라 `cmd.exe`가 파싱하지 못한다(npm이 Windows에서 `cmd.exe /d /s /c`로 실행). CI는 ubuntu이므로 문제가 없다. 로컬에서는 두 절반을 따로 돌린다:

```bash
npm run test --workspaces --if-present    # vitest
.venv/Scripts/python.exe -m pytest        # pytest
.venv/Scripts/python.exe -m mypy backend/src
```

**`npx prettier --check apps`가 104개 파일을 지적하는 것은 진짜 포맷 부채가 아니다.** `core.autocrlf=true`이고 `.gitattributes`가 없어서 Windows 체크아웃이 모든 파일을 CRLF로 받는데, prettier의 기본 `endOfLine: "lf"`가 그것을 전부 걸러낸다. 같은 파일을 git blob(LF)에서 꺼내 검사하면 통과하고, CI는 ubuntu라 애초에 LF다. **104개를 `--write`로 고치면 안 된다** — 무의미한 전 파일 diff가 된다. 자기가 편집한 파일만 `--write`하고, 그 결과가 LF인 것은 `.editorconfig`(`end_of_line = lf`)와 git이 저장하는 형태에 맞는 정상 상태다.

또한 이 워크스테이션에서 `uv`가 인터프리터를 질의할 때 무언가가 자식 프로세스 출력에 `[0x...] ANOMALY: meaningless REX prefix used`를 주입해 `uv sync` / `uv run`이 전부 실패한다(3.13·3.14 동일, 주소 고정 → 주입된 DLL). 우회: `python -m venv .venv` 후 `pip install -e . --group dev`. 잠긴 파일 때문에 `npm ci`도 실패하므로 `npm install`을 쓴다. 이것은 이 머신의 문제이고 저장소의 문제가 아니다.
