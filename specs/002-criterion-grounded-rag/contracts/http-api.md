# HTTP Contract Additions

Criterion version creation adds `job_requirements` and a `verification_guide` per criterion.

```json
{
  "job_requirements": [{
    "requirement_type": "preferred",
    "statement": "ECS 운영 장애 대응 경험",
    "priority": 2,
    "criterion_code": "INCIDENT_RESPONSE"
  }],
  "criteria": [{
    "code": "INCIDENT_RESPONSE",
    "name": "운영 문제 해결",
    "description": "운영 장애의 원인을 분석하고 복구한다.",
    "weight": 30,
    "required": false,
    "verification_guide": {
      "observable_dimensions": ["실제 장애", "원인 분석", "직접 복구", "재발 방지"],
      "strong_answer_signals": ["본인 행동과 판단 근거가 구체적임"],
      "weak_answer_signals": ["팀 활동 또는 결과만 언급함"],
      "follow_up_directions": ["본인 역할", "복구 우선순위"],
      "max_follow_ups": 2,
      "time_budget_seconds": 300
    },
    "abstain_guidance": "최종 답변 근거가 부족하면 판단을 유보한다.",
    "common_questions": ["운영 장애를 해결한 경험을 설명해 주세요."]
  }]
}
```

Review timeline items add optional question rationale with criterion, target type, objective and
SourceReference locators.
