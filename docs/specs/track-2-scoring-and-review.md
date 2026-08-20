# Track 2 — 점수 산술 + 검토 화면

**목표:** LLM은 축별 점수만 만들고, 기준·종합 점수는 순수 산술로 계산한다. 기업 가중치를 실제로 적용하고, "왜 78점인지"를 분모까지 드러내며, 모든 점수가 3단계 안에 영상 구간으로 추적되게 한다.

**전제:** 채점의 역할 분담(`assessment_service.py` 모듈 docstring)은 유지한다 — "모델이 숫자를 정하고, Python은 그 숫자를 보여줘도 되는지 정한다." 우리가 고치는 것은 **그 다음 단계인 집계**다.

**다른 트랙과의 겹침:** 없음. Lane D(`reporting/`)와 company-console `features/review/`만 만진다.

---

## 0. 현재 상태 — `weight`는 저장만 되고 읽히지 않는다

`weight`는 4곳에 존재한다:

| 위치 | 내용 |
| --- | --- |
| `company_management/domain/criteria.py:83` | `weight: float = Field(ge=0)` |
| `company_management/application/company_service.py:55` | `CriterionSnapshot.weight: float` |
| `EvaluationDesigner.tsx:459/477` | range + number 입력 |
| `EvaluationDesigner.tsx:174` | `totalWeight` 계산 — **막대 스케일용으로만 쓰이고 합계 검증 없음** |

**읽는 채점 코드가 하나도 없다.** 집계는 두 개의 단순 평균이다:

```python
# reporting/domain/report.py:139  ReportItem.average_score
scored = [axis.score for axis in self.axis_assessments if axis.score is not None]
return round(sum(scored) / len(scored)) if scored else None

# reporting/domain/report.py:186  Report.overall_score
scored = [item.average_score for item in self.scored_items if item.average_score is not None]
return round(sum(scored) / len(scored)) if scored else None
```

`ASSESSMENT_AXES`(`reporting/application/assessment_prompt.py:65-215`)는 5개 고정 `Final` 튜플이고 `AssessmentAxis`에 **`weight` 필드가 없다** (`key` / `label` / `guidance`만).

**보존해야 할 판단** (`report.py:96-98` docstring): "`score`는 이 축을 판단할 근거가 없을 때 None이다. 절대 0이 아니다 — 0은 지원자가 틀렸다는 뜻이고, '물어보지 않았다'를 틀렸다고 처리하면 우리 면접의 공백으로 사람을 떨어뜨리게 된다."

---

## 1. 선행 작업 — 용어 충돌 해소

`EvaluationDesigner.tsx:367`이 `02 · 평가축`, `:574`가 `평가축 분포`. **여기서 "평가축"은 기업이 정의하는 *평가기준*(`EvaluationCriterion`)이다.** 그런데 LLM 채점의 5개 축(`ASSESSMENT_AXES`: 정확성·깊이·CS 기본기·본인 기여·설명력)도 "축"이다.

2단 가중치를 넣으면 설정 화면에 "축 가중치"가 두 종류 나타난다. 지금 이름으로는 해독 불가능하다. **가중치 작업 전에 반드시 정리한다:**

| 개념 | 코드 | UI 표기 |
| --- | --- | --- |
| 기업이 정의 (가변, 이름·설명·가중치 편집) | `EvaluationCriterion` | **평가기준** |
| LLM 채점 5개 (고정, 비중만 조절) | `AssessmentAxis` | **채점축** |

`EvaluationDesigner.tsx`에서 "평가축" → "평가기준"으로 바꾼다. `design.md:97`도 이미 "평가기준"이라 쓰고 있으므로 문서와 일치하게 된다. 코드 식별자는 이미 `criteria` / `axis`로 갈려 있어 수정 불필요.

---

## 2. 축 가중치 — 5개 고정, 비중만 조절

### 2.1 왜 추가·삭제를 막는가

각 축의 `guidance`(최대 1200자)가 **LLM 프롬프트에 직접 들어간다** (`assessment_prompt.py`). `_known_axis` validator가 `{axis.key for axis in ASSESSMENT_AXES}`에 없는 키를 거부한다. 기업이 임의 축을 추가하면 그 축의 `guidance`를 기업이 써야 하고, 채점 품질이 통제 불가능해진다.

`AssessmentAxis`의 docstring이 이미 이유를 말한다: "축은 회사별이 아니라 고정이다. 축은 엔지니어링 답변을 *읽는 방식*을 기술하고, 회사가 무엇을 중시하는지는 *어떤 기준을 묻는가*에 있다."

**따라서: 축은 5개 고정. 기업은 비중만 조절한다.**

### 2.2 어디에 저장하는가

`AssessmentAxis`에 `weight`를 넣지 않는다 — 그것은 프롬프트 설정이고 `Final` 상수다. 기업별 값이므로 `CompetencyModelVersion`에 둔다:

```python
# company_management/domain/criteria.py
axis_weights: dict[str, float] = Field(default_factory=dict)
# key는 ASSESSMENT_AXES의 key. 빈 dict는 균등 가중(현행 동작)을 뜻한다.
```

빈 dict = 균등을 기본으로 두면 **기존 published 버전이 그대로 동작한다.** 마이그레이션으로 값을 채워 넣지 않는다.

`CriterionVersionSnapshot`(`company_service.py:71-85`)에 `axis_weights`를 추가해 integration 경계를 넘긴다.

### 2.3 검증

기준 가중치·축 가중치 둘 다 `Field(ge=0)`뿐이고 합계 제약이 없다. 합계 검증을 도메인에 넣는다:

- 합계 0은 거부한다 (전부 0이면 나눌 수 없다).
- 합계 100을 **강제하지 않는다.** 대신 정규화한다: `normalized = weight / sum(weights)`. 담당자가 30/25/20을 넣고 합계 75여도 의도대로 동작하는 것이 낫고, 100을 강제하면 기준 하나를 삭제할 때마다 나머지를 다시 맞춰야 한다.
- **정규화한 값을 UI에 보여준다.** `EvaluationDesigner.tsx:376`이 이미 `합계 {totalWeight}`를 표시하므로, 그 옆에 "→ 30% / 25% / ..." 환산값을 붙인다.

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

`Report`는 이미 `version` / `model_version` / `prompt_version` / `config_version` / `kind: AI_ORIGINAL`을 갖고 있고, `kind is not AI_ORIGINAL`이면 생성을 거부한다(`report.py:203`). 같은 원칙을 산술에 적용한다:

`ReportRow`(`reporting/repositories/postgres.py:175`)에 컬럼 추가:

```
scoring_inputs JSON NOT NULL DEFAULT '{}'
```

`{"axis_weights": {...}, "criterion_weights": {...}, "excluded": [{"criterion_id":..., "weight":..., "reason":...}], "numerator": 55.7, "denominator": 0.75}`

**기업이 나중에 가중치를 바꿔도 과거 리포트의 점수와 공식이 변하지 않는다.** `axis_assessments`가 이미 같은 이유로 JSON 배열로 저장된다(`postgres.py:221-223` 주석: "은퇴한 축 키가 저장된 리포트를 읽지 못하게 만들지 않기 위해"). 마이그레이션은 `backend/alembic/versions/reporting/d_002_scoring_inputs.py`.

### 3.4 계산은 어디서 하는가

`Report.overall_score` / `ReportItem.average_score`를 property로 유지하되, **가중치를 인자로 받는 순수 함수로 계산을 옮긴다.** property는 `scoring_inputs`에 동결된 값을 읽어 재현한다. `reporting/domain/scoring.py`(신규)에 계산 함수만 둔다 — 도메인이므로 다른 레인에서 import되지 않는다(`check_module_boundaries.py`의 `PRIVATE_PACKAGES`에 `domain` 포함).

`ReportGenerator.generate`(`workers/reporting/report.py:68`)가 `axis_weights`와 `criterion_weights`를 받아 `Report`에 동결한다. 호출부는 `runtime/worker.py:245` `ReportRequestedEventHandler` — 이미 `self._company.get_criterion_version(...)`으로 `CriterionVersionSnapshot`을 받고 있으므로 `criterion.criteria[i].weight`와 `criterion.axis_weights`를 그대로 넘길 수 있다. **새 조회가 필요 없다.**

`CriterionInput`(`workers/reporting/report.py:38`)에 `weight: float = 1.0`을 추가한다. `runtime/worker.py:228`의 생성부에서 `weight=criterion_item.weight`.

### 3.5 API 응답

`reporting/api/company_routes.py:89` `_report_view`에 추가:

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

---

## 4. 검토 화면 재편

### 4.1 현재 레이아웃

`features/review/ReviewWorkspace.tsx:37-46`:

```
grid-cols-[minmax(280px,0.6fr)_minmax(0,830px)]
[grid-template-areas:'timeline report' 'decision report']
  1180px → 'timeline report' / 'decision decision'
   820px → 단일 컬럼
```

- `TimelineView` (363줄) — `playbackUrl`, `selectedStartMs`, `onSeek`
- `ReportView` (896줄) — 탭 구조 이미 있음: `OverviewPage`(299) / `CriteriaPage`(417) / `FollowUpPage`(736)
- `HumanReview` (238줄)
- 연결: `const [selectedStartMs, setSelectedStartMs] = useState<number|null>(null)` 하나가 타임라인과 리포트를 잇는다. `ReportView.onSelectEvidence` → `setSelectedStartMs` → `TimelineView.selectedStartMs`.

**영상↔리포트 연결 뼈대는 이미 있다.** 새로 만드는 것이 아니라 그 위에 계산기와 비교 뷰를 얹는다.

### 4.2 2단 구조

와이어프레임의 두 화면에 대응:

**① 지원자 개요** — 서류와 면접 요약을 한 화면에서 훑는다.
`design.md:61`에 이미 `/positions/:positionId/applicants/:invitationId` 라우트가 있다. 여기를 개요로 만든다. 제출 자료(자기소개서·GitHub·포트폴리오) 상태와 종합 점수, 그리고 상세 리포트로 가는 버튼.

**② 상세 리포트** — `/review/:sessionId`. 현재 화면을 유지하되:
- 좌측 재생기 + 타임라인 (`TimelineView` — 이미 질문/답변/이벤트 엔트리를 모두 렌더)
- 우측 탭: **AI 리포트 / 계산기 / 후속 확인** — `ReportView`의 기존 3탭 구조를 재사용한다. `OverviewPage`에 계산기를 넣는다.

레이아웃 그리드는 **바꾸지 않는다.** `ReviewWorkspace.tsx`의 주석들이 CSS 우선순위 계산 결과를 기록해 두고 있어(`.review-page-meta > span` (0,1,1) vs `.status-badge` (0,1,0) 등) 재작성하면 그 지식이 사라진다. 탭 내용만 추가한다.

### 4.3 계산기 컴포넌트

`ReportView.tsx`의 `OverviewPage`(299줄)에 들어간다. 이미 `report.overallScore`를 34px로 크게 렌더하고 `toneOf()`로 색을 정한다. 그 아래에 3.2의 표를 붙인다.

`ScoreValue`(796) / `ScoreBar`(812) / `summarizeAxes`(839)가 이미 있으므로 재사용한다. `summarizeAxes`는 축별 평균을 내는데 **가중치를 반영하도록 고친다** — 여기가 화면에서 가중치가 처음 보이는 곳이다.

### 4.4 3단계 추적 보장

요구: 종합 점수 → 기준·축 점수 → Evidence → 영상 구간.

이 연결은 **서버가 보장한다.** 이유: `types.ts:100-108`의 `ReviewEvidenceContext`가 이미 "fetched가 아니라 timeline entries에서 derive된다"고 문서화돼 있고, `buildEvidenceContext(timeline.entries)`가 클라이언트에서 조립한다. 조립 규칙이 프론트에 있으면 엉뚱한 구간이 재생될 수 있고, 근거 플랫폼에서 그것은 치명적이다.

- `AxisAssessment.quoted_evidence_ids`는 이미 서버가 검증한다 — `assessment_service.py`의 `verdict.verified_against(frozenset(answer.evidence_id ...))`가 실재하지 않는 Evidence를 인용한 축의 점수를 죽인다. **이 검증을 유지한다.**
- `Evidence`는 `video_start_ms` / `video_end_ms` / `transcript_segment_id`를 갖고 있다(`_report_view`가 이미 내려준다).
- **추가할 것:** 축 → Evidence → 재생 구간이 한 번의 클릭으로 이어지는지 통합 테스트. `ReportView.tsx:438` `followEvidence(evidence)`가 이미 그 경로다.

### 4.5 사람의 판단은 AI와 섞이지 않는다

`Report.__post_init__`이 `AI_ORIGINAL`이 아닌 kind를 거부한다 — 이 불변식을 유지한다. 사람의 수정은 `HumanReview`로만 기록되고, `ReviewWorkspace.tsx:78`이 `"기업 검토자가 평가 상태를 수정함"`을 고정 사유로 보낸다.

**고정 사유를 자유 입력으로 바꾼다.** 요구사항이 "사유를 기록할 수 있음"인데 지금은 모든 override가 같은 문자열이라 기록의 의미가 없다. `overrideAssessment(reportItemId, assessmentState, reason)` API는 이미 `reason`을 받으므로 UI만 추가한다.

---

## 5. 비교 대시보드

`design.md:60` `/applicants` 라우트가 이미 "전체 지원자 관리"다. 여기에 가중치 적용 점수 열을 추가한다.

- 정렬 가능한 표. `design.md:29-31`의 원칙("반복 업무와 비교가 중심인 조용한 운영 도구", "카드 중첩을 피하고 표 형태의 행")을 따른다.
- **순위가 결정이 아니라는 것을 화면이 말해야 한다.** `unscored_criteria_count`를 점수 옆에 항상 표시한다 — `_report_view`의 주석이 이미 그 이유를 적어 두었다: "82를 읽는 검토자가 세 기준이 채점되지 않았다는 것도 같이 보게 하기 위해."
- 채점 불가 기준이 서로 다른 두 지원자의 점수는 **같은 분모가 아니다.** 표에 분모를 병기하거나, 분모가 다른 행에 표식을 넣는다. 이것을 빼면 비교 대시보드가 잘못된 비교를 만든다.

---

## 6. 오너십 노출 (Track 4에서 넘어온 항목)

`classify_commit_ownership`(`submission_analysis/domain/git_analysis.py`)이 `PRIMARY_OWNED` / `SHARED` / `CONTEXT_ONLY`와 `explanation_codes`를 저장하는데 **담당자가 볼 화면이 없다.** 남의 코드로 만든 질문인지 사람이 판단할 수 있어야 한다.

- 개요 화면(4.2 ①)의 GitHub 항목에 오너십 분류와 `requires_verification`을 표시한다.
- 상세 리포트의 질문 근거(`ReviewQuestionSource`, `QuestionSources` 컴포넌트 `ReportView.tsx:701`)에 그 소스의 오너십을 붙인다.

Track 4가 `candidate_identity_inputs`를 채우기 전까지는 전부 `CONTEXT_ONLY`로 표시된다 — 그것이 정확한 표시다.

---

## 7. 완료 기준

1. `EvaluationDesigner.tsx`에서 기업 기준이 "평가기준"으로 표기되고 "평가축"이 남아 있지 않다.
2. `CompetencyModelVersion.axis_weights`가 존재하고, 빈 dict가 균등 가중으로 동작한다(기존 버전 무변경).
3. 가중치 합계 0은 거부되고, 그 외는 정규화되며, 정규화 결과가 설정 UI에 표시된다.
4. `Report.overall_score`와 `ReportItem.average_score`가 가중평균이고, `score is None`이 분자·분모 양쪽에서 제외된다.
5. `reports.scoring_inputs` 컬럼이 있고 가중치·분자·분모·제외 목록이 동결된다. 기업이 가중치를 바꿔도 기존 리포트 점수가 변하지 않음을 테스트가 검증한다.
6. `/report` 응답에 `scoring_breakdown`이 있고 `numerator` / `denominator`를 포함한다.
7. 계산기가 `55.7 ÷ 0.75 = 74` 형태로 분모를 렌더하고, 제외 항목과 이유를 함께 보여준다.
8. 축 점수 → Evidence → 영상 구간이 클릭 한 번으로 이어지는 통합 테스트가 있다.
9. `score is None`이 어디서도 0으로 렌더되지 않고 평균에 포함되지 않는다.
10. override 사유가 자유 입력이고 `HumanReview`에 저장된다.
11. `/applicants` 비교 표에 가중치 적용 점수 + 미채점 기준 수 + 분모 표식이 있다.
12. `Report.kind is AI_ORIGINAL` 불변식이 유지된다.
13. `npm run typecheck` / `npm test` / `npm run build` 통과.
