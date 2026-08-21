# AI 면접 평가 점수 체계 제안서

> 작성일: 2026-08-19  
> 대상: GBSA 면접 플랫폼 — 면접 종료 후 산출되는 리포트 내 점수 체계  
> 목적: "LLM이 내린 점수"에 대해 채용담당자와 지원자 모두에게 설명 가능한 근거 구조를 마련한다

---

## ⚠️ 이 문서는 요구사항 원본이고, 구현 기준이 아니다 (2026-08-20 갱신)

**구현 기준 문서는 [`docs/specs/track-2-scoring-and-review.md`](specs/track-2-scoring-and-review.md)다.** 이 문서는 그 트랙이 무엇을 요구했는지 남겨 두기 위해 보존하며, 아래 항목은 검토 결과 **채택되지 않았다.** 여기 적힌 코드를 그대로 구현하면 안 된다.

| 이 문서의 항목 | 결정 | 이유 |
| --- | --- | --- |
| §8 Phase 3 · §3.3 "기업 커스텀 축 최대 7개" | **폐기** | 축 `guidance`(1200자)가 채점 시스템 프롬프트에 그대로 렌더된다. 축을 열면 채점 프롬프트 작성 권한을 기업에 넘기는 것이 된다. 회사별 차별화는 개수 제한이 없는 *평가기준*으로 이미 가능하다 |
| §5.2 `AxisAssessment.weight` 필드 추가 | **폐기** | 가중치는 기업 설정이고 `AxisAssessment`는 판단 결과다. `CompetencyModelVersion.axis_weights`에 두고(§5.3과 동일) 리포트에는 `reports.scoring_inputs`로 동결한다 |
| §5.1 `average_score` → `weighted_score` 개명 | **폐기** | `overall_score`는 OpenAPI 계약·생성 타입·프론트에 노출된 공개 필드다. 이름은 유지하고 계산만 `reporting/domain/scoring.py`로 분리한다 |
| §8 Phase 1 "`axis_assessments`에 weight 컬럼" | **정정** | `axis_assessments`는 `report_items`의 JSON 컬럼이므로 추가할 "컬럼"이 없다. 새 마이그레이션은 `reports.scoring_inputs` 하나다 |
| §3.3 "기준선 60점 기업별 설정" | **보류** | Level 3(LLM 입력)을 바꾸는 일이라 집계 트랙과 성질이 다르다. 후속 단계 |
| §8 Phase 4 통계적 신뢰도 | **보류** | 리포트가 immutable이라 재채점 구조가 필요하다 |
| §9.2 지원자 고지 3항목 | **Lane A로 이관** | 고지 문구는 `DEFAULT_CONSENT_POLICY` 도메인 상수이고, 고치면 `policy_version`·`content_digest`가 바뀌어 진행 중인 동의가 무효화된다 |

**산술 오류 정정:** §4 Step 1의 `25.5 + 18.0 + 16.0 + 17.5`은 **77.0**이며 78이 아니다("반올림 78점"도 틀렸다). 그리고 §4 Step 2 예시는 5축 중 CS기본기가 없는데 나머지 4축 가중치가 이미 100%다 — 분모를 드러내지 않으면 어느 계층에서 무엇이 제외됐는지 읽을 수 없다는 것이 트랙 문서 §3.2의 핵심 지적이고, 이 예시가 그 사례다.

**유효한 부분:** §1(현재 구조 분석), §3.1~3.2(3계층 설계와 공식), §4(근거 체인), §6(왜 LLM에 전부 맡기지 않는가), §9.1(현재 준수 사항)은 그대로 채택됐다.

---

## 1. 현재 시스템이 이미 갖추고 있는 것

코드를 분석한 결과, 현재 시스템은 이미 상당히 잘 설계된 평가 구조를 갖고 있습니다.

### 1.1 기존 구조 요약

```
┌─────────────────────────────────────────────────────────────────┐
│  기업 설정 (CompetencyModelVersion)                               │
│  ├── EvaluationCriterion (평가 기준) × N개                        │
│  │   ├── weight (가중치)                                         │
│  │   ├── verification_guide (검증 가이드)                         │
│  │   │   ├── observable_dimensions (관찰 가능한 차원)              │
│  │   │   ├── strong_answer_signals (좋은 답변 시그널)             │
│  │   │   └── weak_answer_signals (약한 답변 시그널)               │
│  │   └── abstain_guidance (판단 유보 기준)                        │
│  └── JobRequirement (직무 요건) × M개                             │
│      └── criterion_code → EvaluationCriterion 참조               │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼  면접 진행
┌─────────────────────────────────────────────────────────────────┐
│  면접 데이터 (InterviewSession)                                   │
│  ├── Turn (질문/답변 턴) × 세션 내 전체                            │
│  ├── TranscriptSegment (자막 구간)                                │
│  └── RecordingAsset (녹화 영상)                                   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼  리포트 생성
┌─────────────────────────────────────────────────────────────────┐
│  Report                                                          │
│  ├── ReportItem (기준별 평가) × 기준 수                            │
│  │   ├── AxisAssessment × 5축                                    │
│  │   │   ├── score (0~100 또는 null)                             │
│  │   │   ├── rationale (근거 설명)                                │
│  │   │   └── quoted_evidence_ids (인용한 Evidence)                │
│  │   ├── Evidence (실제 답변 구간 + 관찰 내용)                     │
│  │   └── assessment_state (confirmed/partial/insufficient)        │
│  └── overall_score (전체 평균)                                    │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 현재 시스템의 5가지 평가 축 (assessment_prompt.py)

| 축 키 | 한글명 | 측정 대상 |
|--------|--------|-----------|
| `correctness` | 정확성 | 기술적 사실의 정확도 |
| `depth` | 깊이 | "왜"와 "대안"까지 내려가는 정도 |
| `fundamentals` | CS 기본기 | 자료구조/알고리즘/네트워크 등 기반 지식 활용 |
| `ownership` | 본인 기여 | 본인이 한 일과 팀이 한 일의 구분 |
| `communication` | 설명력 | 순서, 전달, 모르는 것의 인정 |

### 1.3 현재의 강점 (이미 작동하고 있는 것)

1. **Evidence 기반 인용 필수** — 점수에는 반드시 `quoted_evidence_ids`가 있어야 저장됨
2. **인용 검증** — `verified_against()`가 실제 존재하는 Evidence만 통과시킴
3. **null ≠ 0** — 판단 근거가 없으면 null, 틀렸을 때만 0점
4. **immutable AI 원본** — 생성 후 변경 불가, 사람 결정은 별도 기록
5. **면접 레벨 대응** — 신입/주니어/시니어별로 동일 답변의 기대치가 다름

---

## 2. 문제 정의: 지금 빠져 있는 것

현재 시스템의 점수는 **설명 가능하되, 비교 가능하지 않습니다**.

| 현재 있는 것 | 채용담당자에게 부족한 것 |
|-------------|------------------------|
| 기준별 5축 점수 (0~100) | 수백 명을 한 화면에서 비교할 종합 지표 |
| AI의 축별 rationale | "왜 이 사람이 저 사람보다 높은지" 에 대한 상대적 해석 |
| Evidence 인용 | 인용을 안 읽어도 빠르게 판단할 수 있는 시그널 |
| overall_score (단순 평균) | 기업이 설정한 가중치가 반영된 종합 점수 |
| 축 5개 고정 | 직무별로 중요한 축이 다른 현실 반영 |

### 2.1 핵심 질문

> "수백 명의 면접 리포트를 보는 채용담당자가, 점수만 보고도 신뢰할 수 있으면서,
> 동시에 왜 그 점수인지 3단계 이내로 설명할 수 있는 구조는 무엇인가?"

---

## 3. 제안: 가중 루브릭 기반 점수 체계

### 3.1 설계 원칙

```
┌────────────────────────────────────────────────────────────────────────┐
│                         점수의 설명 가능성 3계층                          │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Level 1: 종합 점수 (Composite Score)                                  │
│  "이 지원자는 78점입니다"                                                │
│  → 채용담당자가 목록에서 빠르게 필터링                                     │
│                                                                        │
│  Level 2: 기준별 가중 점수 (Criterion Weighted Score)                    │
│  "기준 A(가중치 30%)에서 85점, 기준 B(가중치 25%)에서 72점..."             │
│  → 어떤 기준에서 강하고 약한지 확인                                       │
│                                                                        │
│  Level 3: 축별 점수 + 원문 인용 (Axis Score + Evidence Quote)            │
│  "정확성 90점: '~라고 답변함' (02:34~03:12)"                             │
│  → 실제 답변을 확인하고 동의/반론 가능                                    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

**LLM이 하는 일**: Level 3 (축별 점수 + 근거 인용)  
**시스템이 하는 일**: Level 2, Level 1 (가중 합산 = 순수 산술)  
**사람이 하는 일**: 최종 결정 (advance / reject / hold)

이 분리가 핵심입니다:
- LLM은 "이 답변이 이 축에서 몇 점인지"만 판단 (+ 근거 필수)
- 종합 점수는 기업이 설정한 가중치의 **산술 연산**이므로 설명에 LLM이 필요 없음
- "왜 78점인가?" → "기준 A 85점×30% + 기준 B 72점×25% + ... = 78점" (계산기)

### 3.2 점수 산출 공식

```
종합 점수 = Σ (기준별 가중 점수 × 기준 가중치) / Σ (평가된 기준 가중치)

기준별 가중 점수 = Σ (축별 점수 × 축 가중치) / Σ (평가된 축 가중치)

축별 점수 = LLM이 판단 (0~100, 근거 인용 필수, 인용 검증 통과 필수)
```

**중요**: 평가되지 않은 기준/축은 분모에서 **제외**됩니다.  
현재 코드의 `average_score` 프로퍼티가 이미 이 로직을 따르고 있습니다.

### 3.3 현재 코드와의 차이점 (변경이 필요한 부분)

| 항목 | 현재 | 제안 |
|------|------|------|
| 기준별 점수 | 5축 단순 평균 | 축별 가중치 도입 (기업이 설정) |
| 종합 점수 | 기준별 단순 평균 | 기준 가중치(`weight` 필드) 반영 |
| 축 구성 | 5축 고정 | 5축 기본 + 기업 커스텀 축 허용 (선택) |
| 기준선 | 60점 고정 | 기업별 설정 가능 (기본값 60) |
| 비교 뷰 | 없음 | 지원자 간 점수 비교 대시보드 |

---

## 4. 점수의 근거 구조: "왜 이 점수인가?"에 대한 답변 체인

채용담당자가 "왜 78점인가?"라고 물었을 때, 시스템이 3단계로 답합니다:

### Step 1: 공식 투명성

```
종합 78점 = 
  시스템설계(85점) × 30% = 25.5
  + 문제해결(72점) × 25% = 18.0
  + 협업경험(80점) × 20% = 16.0
  + 기술깊이(70점) × 25% = 17.5
  ─────────────────────────
  합계: 77.0 → 반올림 78점
  
  * "협업경험" 축 1개(CS기본기)는 답변 근거 없어 제외됨
```

이 단계는 **순수 산술**입니다. LLM 판단이 아니라 기업이 설정한 가중치의 연산입니다.

### Step 2: 기준별 근거

```
시스템설계 85점 =
  정확성 90점 (가중 25%) — "CAP 정리 설명이 정확하고 트레이드오프 명시"
  깊이   85점 (가중 30%) — "대안으로 eventual consistency를 검토한 이유 설명"
  본인기여 80점 (가중 25%) — "본인이 설계한 부분과 팀 결정을 명확히 분리"
  설명력  85점 (가중 20%) — "복잡한 구조를 단계별로 설명"
```

이 단계도 산술 + LLM의 rationale입니다.

### Step 3: 원문 확인

```
정확성 90점의 근거:
  Evidence #1 (02:34~03:12):
  "저는 CAP에서 AP를 선택했는데, 이유는 우리 서비스가 가용성이 더 중요하고
   일관성은 eventual consistency로 2초 이내에 수렴하면 비즈니스 요구사항을
   충족하기 때문입니다."
  
  AI 판단: 용어를 정확히 사용하고, 인과가 바르며, 근거 있는 판단.
           "정확하게 설명했지만 consistency 수렴 2초의 측정 근거가 없어
            만점에서 감점" → 90점
```

이 단계에서 채용담당자는 **영상을 재생**하거나 **텍스트를 읽고** 동의/반론할 수 있습니다.

---

## 5. 구현 설계: 코드 레벨

### 5.1 기존 코드 활용 (변경 최소화)

현재 시스템은 이미 대부분의 인프라를 갖추고 있습니다:

```python
# 현재 report.py의 ReportItem.average_score (단순 평균)
@property
def average_score(self) -> int | None:
    scored = [axis.score for axis in self.axis_assessments if axis.score is not None]
    return round(sum(scored) / len(scored)) if scored else None
```

**변경 제안**: 축별 가중치를 반영한 가중 평균으로 변경

```python
# 제안: 축별 가중치 반영
@property
def weighted_score(self) -> int | None:
    scored = [
        (axis.score, axis.weight)
        for axis in self.axis_assessments
        if axis.score is not None
    ]
    if not scored:
        return None
    total_weight = sum(weight for _, weight in scored)
    weighted_sum = sum(score * weight for score, weight in scored)
    return round(weighted_sum / total_weight)
```

```python
# 현재 report.py의 Report.overall_score (기준별 단순 평균)
@property
def overall_score(self) -> int | None:
    scored = [
        item.average_score for item in self.scored_items if item.average_score is not None
    ]
    return round(sum(scored) / len(scored)) if scored else None
```

**변경 제안**: 기준별 가중치(`EvaluationCriterion.weight`)를 반영

```python
# 제안: 기준 가중치 반영
@property
def weighted_overall_score(self) -> int | None:
    scored = [
        (item.weighted_score, item.criterion_weight)
        for item in self.items
        if item.weighted_score is not None
    ]
    if not scored:
        return None
    total_weight = sum(weight for _, weight in scored)
    weighted_sum = sum(score * weight for score, weight in scored)
    return round(weighted_sum / total_weight)
```

### 5.2 신규 데이터 모델

```python
# 축별 가중치를 AxisAssessment에 추가 (현재는 없음)
@dataclass(frozen=True, slots=True)
class AxisAssessment:
    axis: str
    label: str
    score: int | None
    rationale: str
    weight: float = 1.0  # ← 신규: 기본 동일 가중치
    quoted_evidence_ids: tuple[UUID, ...] = ()
```

```python
# ReportItem에 기준 가중치 스냅샷 추가
@dataclass(frozen=True, slots=True)
class ReportItem:
    # ... 기존 필드들 ...
    criterion_weight: float = 1.0  # ← 신규: 기준 가중치 스냅샷
```

### 5.3 기업 설정 확장 (CompetencyModelVersion)

현재 `EvaluationCriterion`에 이미 `weight: float` 필드가 있습니다.  
이 필드가 종합 점수 산출에 반영되도록 파이프라인을 연결하면 됩니다.

추가로 축별 가중치를 기업이 설정할 수 있도록:

```python
class AxisWeightConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    correctness: float = Field(default=1.0, ge=0.0, le=5.0)
    depth: float = Field(default=1.0, ge=0.0, le=5.0)
    fundamentals: float = Field(default=1.0, ge=0.0, le=5.0)
    ownership: float = Field(default=1.0, ge=0.0, le=5.0)
    communication: float = Field(default=1.0, ge=0.0, le=5.0)
```

---

## 6. "왜 LLM한테 전부 맡기면 안 되는가"에 대한 답

### 6.1 현재 시스템이 이미 해결한 것

| 우려 | 시스템의 대응 |
|------|-------------|
| LLM이 거짓 근거를 댈 수 있다 | `verified_against()`로 인용 검증. 실제 Evidence가 아니면 점수 삭제 |
| LLM 점수가 일관적이지 않을 수 있다 | `temperature=0.1`로 near-deterministic 설정 |
| 같은 답변을 다르게 평가할 수 있다 | 리포트는 immutable, 한 번 생성 후 변경 불가 |
| 제출물 양으로 평가할 수 있다 | 프롬프트에 "분량, 커밋 수, 유사도는 평가에 쓰지 않습니다" 명시 |
| 묻지 않은 것을 감점할 수 있다 | "답변에서 다루지 않은 주제를 몰랐다고 감점하지 않습니다" 규칙 |

### 6.2 추가로 필요한 보호 장치

```
┌──────────────────────────────────────────────────────────────────┐
│  점수의 신뢰성을 보장하는 4중 장치                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  1. 인용 검증 (Evidence Verification) ← 이미 구현됨                │
│     - LLM 점수 → quoted_evidence_ids 필수                         │
│     - evidence_id가 실제 존재하지 않으면 점수 삭제                   │
│                                                                   │
│  2. 범위 검증 (Range Verification) ← 이미 구현됨                   │
│     - Evidence가 유효한 영상 구간 내에 있는지                        │
│     - 녹화 누락 구간과 겹치면 거부                                   │
│                                                                   │
│  3. 산술 투명성 (Arithmetic Transparency) ← 제안                   │
│     - 종합 점수 = 기업 가중치의 산술 연산                            │
│     - LLM이 종합 점수를 내는 게 아님 → 공식 추적 가능                │
│                                                                   │
│  4. 사람 오버라이드 (Human Override) ← 이미 구현됨                  │
│     - assessment_override로 AI 판단을 덮을 수 있음                  │
│     - final_decision은 반드시 사람만 가능                            │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

### 6.3 설명 가능성 체크리스트

| 질문 | 시스템의 답변 방식 |
|------|-------------------|
| "왜 이 점수인가?" | 가중치 공식 (산술) + 축별 근거 (LLM) + 원문 인용 (영상) |
| "왜 A가 B보다 높은가?" | 동일 기준의 축별 점수 비교 + 각각의 인용 비교 |
| "이 점수가 맞는가?" | Evidence 재생 → 사람이 확인 → 동의 또는 override |
| "어떤 기준으로 평가했는가?" | 기업이 설정한 CompetencyModelVersion (버전 관리됨) |
| "LLM 판단이 편향되지 않았는가?" | 프롬프트 규칙 8: 신상 정보 평가 반영 금지, 온도 0.1 |

---

## 7. 채용담당자 관점: 수백 명을 비교하는 시나리오

### 7.1 1차 필터: 종합 점수 기반 정렬

```
┌───────────────────────────────────────────────────────────┐
│  포지션: 백엔드 시니어 (20명 지원)                           │
├───────────────────────────────────────────────────────────┤
│  순위  이름      종합점수  상태        주요 강점              │
│  1    김○○     85점     확인됨      시스템설계·깊이 탁월     │
│  2    이○○     82점     확인됨      정확성·CS기본기 우수     │
│  3    박○○     78점     부분확인    본인기여가 탁월          │
│  ...                                                      │
│  18   최○○     45점     근거부족    전반적으로 표면적        │
│  19   정○○     —       판단불가    녹화 이슈               │
│  20   한○○     38점     추가확인    정확성에서 오류 다수     │
└───────────────────────────────────────────────────────────┘
```

### 7.2 2차 비교: 기준별 점수 비교

```
기준: 시스템 설계 (가중치 30%)
┌─────────────────────────────────────────────────────────────┐
│  이름    정확성  깊이   CS기본기  본인기여  설명력  기준점수    │
│  김○○   90     92     80       85       88     87점       │
│  이○○   95     75     90       70       82     83점       │
│  박○○   70     68     75       95       72     76점       │
└─────────────────────────────────────────────────────────────┘
```

### 7.3 3차 확인: 개별 근거 검토

현재의 ReportView.tsx가 이미 이 기능을 제공합니다:
- 축별 점수 + rationale 표시
- Evidence 인용 → 클릭 시 영상 해당 구간 재생
- 사람 오버라이드 드롭다운

---

## 8. 구현 로드맵

### Phase 1: 가중치 반영 (기존 코드 확장)

**영향 범위**: `report.py`, `assessment_service.py`, `ReportView.tsx`  
**난이도**: 낮음 (기존 weight 필드 활용)

- [ ] `ReportItem.average_score` → `weighted_score`로 교체
- [ ] `Report.overall_score` → 기준 가중치 반영
- [ ] `AxisAssessment`에 weight 필드 추가 (마이그레이션)
- [ ] 리포트 생성 시 기준 weight를 ReportItem에 스냅샷

### Phase 2: 비교 대시보드 (프론트엔드)

**영향 범위**: `company-console` 신규 컴포넌트  
**난이도**: 중간

- [ ] 포지션별 지원자 점수 목록 뷰
- [ ] 기준별 비교 뷰 (테이블)
- [ ] 축별 레이더 차트 (개인별)
- [ ] 점수 산출 과정 펼침 (종합 → 기준 → 축 → Evidence)

### Phase 3: 기업 커스텀 축 (선택적 확장)

**영향 범위**: `assessment_prompt.py`, `criteria.py`, Hiring UI  
**난이도**: 높음 (프롬프트 동적 생성)

- [ ] 기업이 축 추가/제거 가능 (최대 7개)
- [ ] 축별 guidance를 기업이 직접 작성
- [ ] 커스텀 축의 점수도 동일한 인용 검증 적용

### Phase 4: 통계적 신뢰도 표시 (장기)

**영향 범위**: 신규 모듈  
**난이도**: 높음

- [ ] 동일 답변 재평가 시 점수 분산 측정
- [ ] 분산이 큰 축/기준에 "신뢰도 낮음" 표시
- [ ] 기업에 "이 점수는 ±5점 범위로 읽으세요" 가이드

---

## 9. 법적/윤리적 고려사항

### 9.1 현재 코드가 이미 준수하는 것

1. **AI가 최종 결정을 내리지 않음** — `HumanReview.final_decision`은 `ActorType.COMPANY_USER`만 가능
2. **개인 신상 정보 배제** — 프롬프트 규칙 8에 명시
3. **immutable 리포트** — 생성 후 변경 불가, 수정은 별도 review로 기록
4. **리포트 UI 고지** — "합격 여부를 판단한 점수가 아닙니다" 문구 상시 표시

### 9.2 추가로 고려할 것

- 점수 산출 공식을 채용공고 또는 지원자 동의 과정에서 고지
- "AI 평가에 이의를 제기할 수 있습니다" 안내 (GDPR Article 22 유사 대응)
- 기업별 점수 분포의 편향 모니터링 (특정 그룹 일관적 저점 감지)

---

## 10. 요약: 점수의 설명 가능한 근거 체계

```
┌──────────────────────────────────────────────────────────────┐
│                                                               │
│  "이 지원자는 78점입니다"                                       │
│                                                               │
│  왜? ─────────────────────────────────────────────────────┐   │
│  │                                                        │   │
│  │  기업이 설정한 가중치로 산술 계산했기 때문입니다.            │   │
│  │  시스템설계 85×0.3 + 문제해결 72×0.25 + ...             │   │
│  │                                                        │   │
│  │  그 기준별 점수는 왜? ────────────────────────────────┐ │   │
│  │  │                                                   │ │   │
│  │  │  5개 축을 가중 평균했기 때문입니다.                   │ │   │
│  │  │  정확성 90×0.25 + 깊이 85×0.3 + ...              │ │   │
│  │  │                                                   │ │   │
│  │  │  그 축별 점수는 왜? ─────────────────────────────┐│ │   │
│  │  │  │                                              ││ │   │
│  │  │  │  LLM이 실제 답변을 읽고 판단했습니다.           ││ │   │
│  │  │  │  근거: "CAP에서 AP를 선택한 이유는..."         ││ │   │
│  │  │  │  영상 구간: 02:34~03:12                      ││ │   │
│  │  │  │  → [재생 버튼]으로 직접 확인 가능              ││ │   │
│  │  │  │                                              ││ │   │
│  │  │  │  동의하지 않으면?                              ││ │   │
│  │  │  │  → 사람 오버라이드로 변경 + 사유 기록           ││ │   │
│  │  │  └──────────────────────────────────────────────┘│ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                               │
│  최종 결정: 사람만 가능 (advance / reject / hold)               │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

**결론**: LLM은 "이 답변이 이 기준의 이 축에서 어떤 수준인가"만 판단하고,  
종합 점수는 기업이 설정한 가중치의 **산술 연산**으로 산출합니다.  
모든 점수는 영상 원문까지 3단계 이내로 추적 가능하며,  
사람은 언제든 AI 판단을 덮고 그 사유를 기록할 수 있습니다.

---

## 부록: 현재 코드 핵심 파일 참조

| 관심 영역 | 파일 경로 |
|-----------|----------|
| 점수 도메인 모델 | `backend/src/interview_evidence/reporting/domain/report.py` |
| 평가 프롬프트 | `backend/src/interview_evidence/reporting/application/assessment_prompt.py` |
| 평가 서비스 | `backend/src/interview_evidence/reporting/application/assessment_service.py` |
| 리포트 생성기 | `backend/src/interview_evidence/workers/reporting/report.py` |
| 기업 평가 기준 | `backend/src/interview_evidence/company_management/domain/criteria.py` |
| 사람 리뷰 도메인 | `backend/src/interview_evidence/reporting/domain/review.py` |
| 리뷰 서비스 | `backend/src/interview_evidence/reporting/application/review_service.py` |
| 프론트 리포트 뷰 | `apps/company-console/src/features/review/ReportView.tsx` |
| 프론트 사람 리뷰 | `apps/company-console/src/features/review/HumanReview.tsx` |
| 면접 레벨 정의 | `backend/src/interview_evidence/shared/interview_level.py` |
| 검증 맵 빌더 | `backend/src/interview_evidence/submission_analysis/application/verification_map.py` |
