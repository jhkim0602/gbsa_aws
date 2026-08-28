# WhyYou — Interview Evidence Platform

WhyYou는 지원자의 이력서·포트폴리오·GitHub 활동과 실시간 면접 답변을 하나의 근거 체계로 연결하는 AI 채용 플랫폼입니다. 기업은 포지션과 평가 기준을 설계하고, 지원자는 AI 면접을 진행하며, 채용 담당자는 원문·영상 타임라인까지 추적 가능한 리포트와 채용 어시스턴트를 통해 최종 판단을 내릴 수 있습니다.

> AI는 판단을 대신하지 않습니다. 흩어진 증거를 구조화하고 검토 가능한 형태로 제공하며, 최종 의사결정은 채용 담당자가 수행합니다.

## 주요 기능

- 포지션, 평가 기준, 필수 질문, 초대 일정 및 지원자 파이프라인 관리
- PDF·문서와 GitHub 저장소 분석을 통한 지원자별 면접 전략 생성
- WebSocket 기반 실시간 AI 면접, 음성 인식·합성, 중단 세션 재개
- 평가 기준별 점수와 원문 인용, 영상 타임라인이 포함된 근거 중심 리포트
- `pgvector` 기반 RAG 채용 어시스턴트와 지원자 비교·탐색
- Outbox, SQS 재시도·DLQ, 멱등 처리, ECS Task Protection 기반 복구
- 예약 인원과 큐 적체를 반영한 API/Worker 자동 확장

## 아키텍처

![WhyYou AWS/GCP 하이브리드 아키텍처](docs/architecture/interview-evidence-aws-gcp-hybrid.png)

| 영역         | 구성                                                   |
| ------------ | ------------------------------------------------------ |
| Web          | React 18, TypeScript, Vite, CloudFront, S3             |
| API / Worker | FastAPI, Python 3.12, ECS Fargate, ALB                 |
| 데이터       | Aurora PostgreSQL Serverless v2, pgvector, S3          |
| 비동기 처리  | SQS, DLQ, Transactional Outbox                         |
| 인증         | Amazon Cognito                                         |
| AI           | Vertex AI Gemini 또는 Amazon Bedrock, Titan Embeddings |
| 문서·음성    | GCP Document AI, Speech-to-Text, Text-to-Speech        |
| 인프라·관측  | Terraform, CloudWatch, OpenTelemetry, X-Ray            |

브라우저는 CloudFront의 동일 출처 `/v1` 경로를 통해 API와 WebSocket에 연결합니다. API는 실시간 면접을 담당하고, 시간이 오래 걸리는 문서·미디어·리포트 처리는 SQS를 통해 Worker로 분리됩니다. 운영 환경의 인프라는 Terraform으로 관리합니다.

## 저장소 구조

```text
.
├── apps/
│   ├── company-console/       # 기업용 채용 운영 SPA
│   └── applicant-interview/   # 지원자용 AI 면접 SPA
├── backend/
│   ├── src/interview_evidence # FastAPI 모듈러 모놀리스와 Worker
│   ├── alembic/               # 데이터베이스 마이그레이션
│   └── tests/                 # Python 테스트
├── packages/
│   ├── contracts/             # OpenAPI 기반 공유 계약
│   └── design-system/         # 공통 디자인 토큰
├── infra/
│   ├── environments/          # bootstrap, dev, prod Terraform root
│   ├── modules/               # 재사용 가능한 AWS 모듈
│   └── tests/                 # Terraform 테스트
├── docs/                      # 개발·설계·운영 문서
├── tests/                     # 계약, E2E, 회귀, 부하 테스트
├── compose.yaml               # 로컬 Postgres, LocalStack, Mailpit
└── Makefile                   # 개발 및 검증 명령
```

## 로컬 실행

### 사전 요구사항

- Node.js 22 이상 (`package.json` 최소 요구 버전은 20)
- Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)
- Docker와 Docker Compose
- 실제 AI·음성·OCR 기능을 사용할 AWS/GCP 자격 증명

### 1. 의존성과 환경 구성

```bash
make dev-install
cp .env.example .env
```

`.env`의 AWS/GCP 항목을 채우고 기업 콘솔의 로컬 설정을 만듭니다.

```bash
cp apps/company-console/.env.example apps/company-console/.env.local
```

두 파일의 로컬 회사 토큰이 일치해야 합니다. 서비스 계정 JSON, 토큰, 비밀번호 등 비밀값은 커밋하지 마세요.

### 2. 로컬 인프라 시작

```bash
make up
```

다음 서비스가 시작되고 S3 버킷·SQS 큐 생성과 Alembic 마이그레이션이 실행됩니다.

| 서비스                | 주소                    | 용도                               |
| --------------------- | ----------------------- | ---------------------------------- |
| PostgreSQL + pgvector | `localhost:5432`        | 애플리케이션 데이터와 벡터 검색    |
| LocalStack            | `localhost:4566`        | 로컬 S3, SQS, SES, Secrets Manager |
| Mailpit               | <http://localhost:8025> | 초대 이메일 확인                   |

### 3. 애플리케이션 실행

각 명령을 별도 터미널에서 실행합니다.

```bash
make api                  # API: http://localhost:8080
make worker               # 기본 4개 Worker
npm run dev:company       # 기업 콘솔: http://localhost:5173
npm run dev:applicant     # 지원자 면접: http://localhost:5174
```

준비 상태는 다음 명령으로 확인합니다.

```bash
curl -s http://localhost:8080/health/ready
```

종료할 때는 `make down`을 실행합니다. Windows PowerShell 사용자는 [`scripts/local.ps1`](scripts/local.ps1), 상세한 설정과 문제 해결은 [`docs/local-development.md`](docs/local-development.md)를 참고하세요.

> **비용 주의:** 로컬 컨테이너가 대체하는 서비스는 PostgreSQL, S3, SQS, SES, Secrets Manager, SMTP뿐입니다. Vertex AI, GCP Speech/Document AI, Bedrock, MediaConvert 등은 설정된 실제 클라우드 계정으로 호출되며 비용이 발생할 수 있습니다.

## 개발 명령

```bash
make dev-install          # 로컬 개발용 editable 의존성 설치
make bootstrap            # CI/이미지와 같은 non-editable 설치
make migrate              # Alembic 마이그레이션 적용
make assistant-backfill   # 누락되거나 오래된 RAG 문서 재생성

npm run format:check      # Prettier + Ruff 포맷 검사
npm run lint              # ESLint + Ruff
npm run typecheck         # TypeScript + mypy
npm test                  # 프런트엔드 + Python 테스트
npm run build             # 전체 워크스페이스 빌드

make infra-format-check   # Terraform 포맷 검사
make infra-validate       # dev/prod Terraform root 검증
```

코드를 자동 정리하려면 `npm run format`을 사용합니다. Worker 수는 `WORKER_CONCURRENCY=2 make worker`처럼 조정할 수 있습니다.

## 브랜치와 배포

- `develop`: 통합 개발 브랜치
- `main`: 운영 기준 브랜치
- Pull Request가 `develop` 또는 `main`을 대상으로 열리면 애플리케이션·인프라 CI가 실행됩니다.
- `main` 대상 Pull Request가 병합되면 저장된 Terraform plan 승인·적용, 이미지 배포, 프런트엔드 배포 순서로 운영 배포가 진행됩니다.
- 개발 환경의 생성·업데이트·삭제는 `Manage Dev Infrastructure` 워크플로를 `main`에서 수동 실행합니다.

직접 push는 운영 배포 워크플로의 트리거가 아닙니다. 운영 변경은 원칙적으로 Pull Request와 승인 환경을 거쳐 진행하세요.

## 추가 문서

- [로컬 개발 가이드](docs/local-development.md)
- [신뢰성·관측성·예약 용량 설계](docs/specs/reliability-observability-scheduled-capacity-plan.md)
- [평가 시스템 제안](docs/scoring-system-proposal.md)

## 라이선스

현재 저장소에는 별도 오픈소스 라이선스가 선언되어 있지 않습니다.
