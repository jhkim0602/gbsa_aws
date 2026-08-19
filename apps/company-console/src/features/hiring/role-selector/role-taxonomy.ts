export type RoleLevel = "주니어" | "미들" | "시니어";

export interface RoleTemplate {
  id: string;
  label: string;
  description: string;
  techStack: string[];
  responsibilities: string[];
  requirements: string[];
  preferred: string[];
  focusAreas: string[];
  teamCulture: string[];
}

export interface RoleCategoryTemplate {
  id: string;
  label: string;
  description: string;
  roles: RoleTemplate[];
}

export const ROLE_LEVEL_OPTIONS: RoleLevel[] = ["주니어", "미들", "시니어"];

export const LEVEL_GUIDE: Record<RoleLevel, string> = {
  주니어: "기본기와 실행력을 검증하는 질문 비중을 높입니다.",
  미들: "설계 근거와 협업 의사결정 검증 비중을 높입니다.",
  시니어: "아키텍처 판단과 리더십/트레이드오프 검증 비중을 높입니다.",
};

export const ROLE_TRACK_CATEGORIES: RoleCategoryTemplate[] = [
  {
    id: "backend",
    label: "Backend",
    description: "서비스 서버와 공통 플랫폼을 설계하고 운영합니다.",
    roles: [
      {
        id: "backend-service",
        label: "서비스 백엔드",
        description: "사용자 기능, 도메인 로직, API 운영 중심",
        techStack: ["Java", "Spring Boot", "Node.js", "SQL", "Redis", "AWS"],
        responsibilities: ["도메인 로직 설계 및 구현", "외부/내부 API 운영", "데이터 정합성 관리", "운영 장애 대응"],
        requirements: ["실서비스 API 개발 경험", "RDBMS 설계 및 쿼리 최적화 경험", "테스트 코드 작성 경험", "운영 환경 이슈 해결 경험"],
        preferred: ["대용량 트래픽 처리 경험", "비동기 메시징 경험", "클라우드 운영 경험"],
        focusAreas: ["API 설계", "도메인 모델링", "트랜잭션 처리", "장애 대응", "테스트 전략", "협업"],
        teamCulture: ["문제 원인 공유", "코드 리뷰 중심 개선", "지표 기반 의사결정"],
      },
      {
        id: "backend-platform",
        label: "플랫폼 백엔드",
        description: "공통 모듈, 개발 생산성, 내부 플랫폼 중심",
        techStack: ["Java", "Kotlin", "Go", "Kubernetes", "Kafka", "Terraform"],
        responsibilities: ["공통 서비스 모듈 설계", "내부 플랫폼/API 제공", "개발 워크플로우 개선", "운영 표준화"],
        requirements: ["공통 시스템 설계 경험", "분산 시스템 이해", "운영 자동화 경험", "여러 팀 협업 경험"],
        preferred: ["플랫폼 제품화 경험", "관측성 체계 구축 경험", "멀티 테넌시 설계 경험"],
        focusAreas: ["시스템 경계", "표준화", "운영 자동화", "관측성", "확장성", "내부 고객 관점"],
        teamCulture: ["재사용 우선", "작은 개선의 누적", "문서 기반 협업"],
      },
      {
        id: "backend-data-api",
        label: "데이터/API 백엔드",
        description: "외부 연동, 데이터 처리, 배치/비동기 흐름 중심",
        techStack: ["Python", "Node.js", "Kafka", "PostgreSQL", "Redis", "Docker"],
        responsibilities: ["외부 시스템 연동", "배치 및 이벤트 처리", "데이터 파이프라인 운영", "정합성 검증"],
        requirements: ["비동기 처리 경험", "외부 API 연동 경험", "데이터 가공 경험", "운영 로그 분석 경험"],
        preferred: ["ETL/ELT 경험", "워크플로우 오케스트레이션 경험", "데이터 품질 운영 경험"],
        focusAreas: ["외부 연동", "비동기 흐름", "데이터 정합성", "배치 운영", "에러 복구", "모니터링"],
        teamCulture: ["안정성 우선", "명확한 계약 관리", "재현 가능한 운영"],
      },
      {
        id: "backend-transaction",
        label: "트랜잭션 백엔드",
        description: "주문, 결제, 정산 등 정합성 중심 서비스",
        techStack: ["Java", "Spring", "MySQL", "Kafka", "Redis", "Docker"],
        responsibilities: ["핵심 트랜잭션 설계", "락/동시성 제어", "이벤트 기반 후처리", "장애 복구 시나리오 관리"],
        requirements: ["결제/주문/정산 등 상태 전이 경험", "트랜잭션/락 이해", "데이터 복구 경험", "운영 리스크 관리 경험"],
        preferred: ["대규모 커머스 경험", "감사 로그 체계 경험", "정산 도메인 경험"],
        focusAreas: ["정합성", "동시성 제어", "상태 전이", "복구 전략", "리스크 관리", "운영 판단"],
        teamCulture: ["변경 리스크 최소화", "사전 검증 강화", "장애 후 학습 공유"],
      },
    ],
  },
  {
    id: "frontend",
    label: "Frontend",
    description: "웹 사용자 경험과 제품 인터페이스를 구현합니다.",
    roles: [
      {
        id: "frontend-product",
        label: "프로덕트 프론트엔드",
        description: "사용자 기능과 제품 흐름 구현 중심",
        techStack: ["TypeScript", "React", "Next.js", "CSS", "TanStack Query", "Jest"],
        responsibilities: ["제품 화면 설계 및 구현", "상태 흐름 관리", "사용성 개선", "디자인 협업"],
        requirements: ["React 기반 개발 경험", "상태관리 경험", "웹 성능 개선 경험", "협업 도구 사용 경험"],
        preferred: ["SSR/ISR 경험", "접근성 개선 경험", "A/B 테스트 경험"],
        focusAreas: ["컴포넌트 설계", "상태 관리", "사용자 흐름", "접근성", "성능 최적화", "협업"],
        teamCulture: ["사용자 경험 중심", "빠른 피드백 반영", "디자인-개발 협업"],
      },
      {
        id: "frontend-platform",
        label: "플랫폼 프론트엔드",
        description: "디자인 시스템과 공통 UI 인프라 중심",
        techStack: ["TypeScript", "React", "Storybook", "Vite", "Playwright", "Monorepo"],
        responsibilities: ["공통 컴포넌트 설계", "디자인 토큰/시스템 운영", "프론트엔드 표준화", "개발 생산성 개선"],
        requirements: ["컴포넌트 아키텍처 경험", "문서화 경험", "테스트 가능한 UI 설계 경험", "여러 팀 협업 경험"],
        preferred: ["디자인 시스템 구축 경험", "모노레포 경험", "릴리즈 자동화 경험"],
        focusAreas: ["재사용성", "UI 표준화", "테스트 전략", "개발 경험", "문서화", "협업 구조"],
        teamCulture: ["기준을 먼저 정리", "작은 단위 배포", "장기 유지보수 관점"],
      },
      {
        id: "frontend-interaction",
        label: "UI 인터랙션 엔지니어",
        description: "복잡한 상호작용과 화면 완성도 중심",
        techStack: ["React", "TypeScript", "Motion", "Canvas", "CSS", "Figma"],
        responsibilities: ["고난도 UI 인터랙션 구현", "애니메이션 품질 개선", "상태 전이 설계", "세밀한 화면 완성도 관리"],
        requirements: ["복잡한 UI 구현 경험", "렌더링 동작 이해", "브라우저 성능 이슈 대응 경험", "디자인 정합성 관리 경험"],
        preferred: ["캔버스/WebGL 경험", "모션 가이드 경험", "실시간 UI 경험"],
        focusAreas: ["인터랙션 설계", "렌더링 성능", "상태 전이", "화면 완성도", "접근성", "디자인 정합성"],
        teamCulture: ["디테일 중시", "사용자 체감 우선", "디자인 의도 존중"],
      },
      {
        id: "frontend-webapp",
        label: "웹 애플리케이션 프론트엔드",
        description: "대시보드, 업무도구, 데이터 화면 중심",
        techStack: ["React", "TypeScript", "Next.js", "Chart", "Table", "Zustand"],
        responsibilities: ["복잡한 업무 화면 구현", "테이블/폼/차트 설계", "권한별 UI 분기 처리", "운영 이슈 대응"],
        requirements: ["웹앱 개발 경험", "폼/테이블 중심 UI 경험", "권한/상태 분기 경험", "실서비스 유지보수 경험"],
        preferred: ["B2B SaaS 경험", "대규모 화면 리팩토링 경험", "로그 기반 디버깅 경험"],
        focusAreas: ["정보 구조", "복잡한 상태 관리", "업무 흐름", "성능 안정성", "에러 처리", "운영 대응"],
        teamCulture: ["명확한 정보 전달", "운영 친화적 구현", "현실적인 개선 우선"],
      },
    ],
  },
  {
    id: "mobile",
    label: "Mobile",
    description: "모바일 앱을 개발하고 배포 및 운영합니다.",
    roles: [
      {
        id: "mobile-android",
        label: "Android 개발자",
        description: "Android 네이티브 앱 개발",
        techStack: ["Kotlin", "Android", "Jetpack", "Coroutines", "Room", "Firebase"],
        responsibilities: ["앱 기능 개발 및 개선", "앱 성능 최적화", "크래시 분석", "스토어 배포 운영"],
        requirements: ["Android 개발 경험", "비동기 처리 이해", "네트워크 통신 경험", "앱 아키텍처 경험"],
        preferred: ["모듈화 아키텍처 경험", "테스트 자동화 경험", "모니터링 도구 경험"],
        focusAreas: ["앱 아키텍처", "비동기 처리", "성능 최적화", "크래시 대응", "릴리즈 전략", "품질 관리"],
        teamCulture: ["안정적 릴리즈", "사용자 피드백 반영", "품질 자동화"],
      },
      {
        id: "mobile-ios",
        label: "iOS 개발자",
        description: "iOS 네이티브 앱 개발",
        techStack: ["Swift", "iOS", "SwiftUI", "UIKit", "Combine", "Firebase"],
        responsibilities: ["핵심 플로우 구현", "앱 구조 개선", "메모리/성능 최적화", "릴리즈 운영"],
        requirements: ["Swift 기반 개발 경험", "네트워크/상태 관리 경험", "디버깅 경험", "UI 구현 경험"],
        preferred: ["SwiftUI/UIKit 혼합 경험", "A/B 테스트 경험", "자동화 파이프라인 경험"],
        focusAreas: ["UI 아키텍처", "상태 관리", "성능/메모리", "릴리즈 전략", "문제 해결", "협업"],
        teamCulture: ["일관된 사용자 경험", "학습 공유 문화", "품질 중심"],
      },
      {
        id: "mobile-crossplatform",
        label: "크로스플랫폼 앱 개발자",
        description: "Flutter 또는 React Native 기반 개발",
        techStack: ["Flutter", "Dart", "React Native", "TypeScript", "Firebase", "CI/CD"],
        responsibilities: ["공통 컴포넌트 설계", "플랫폼 차이 대응", "빌드/배포 자동화", "성능 및 UX 개선"],
        requirements: ["Flutter 또는 RN 경험", "플랫폼별 차이 대응 경험", "상태 관리 경험", "배포 경험"],
        preferred: ["네이티브 브릿지 경험", "모듈화 설계 경험", "테스트 자동화 경험"],
        focusAreas: ["플랫폼 호환성", "상태 관리", "배포 자동화", "성능 개선", "사용성", "운영 대응"],
        teamCulture: ["빠른 반복", "플랫폼 일관성", "협업 자동화"],
      },
      {
        id: "mobile-platform",
        label: "모바일 플랫폼 엔지니어",
        description: "공통 SDK, 인프라, 빌드 체계 중심",
        techStack: ["Kotlin", "Swift", "CI/CD", "Fastlane", "Firebase", "Gradle"],
        responsibilities: ["모바일 공통 모듈 운영", "빌드 체계 개선", "릴리즈 파이프라인 관리", "앱 공통 SDK 제공"],
        requirements: ["모바일 플랫폼 또는 공통 모듈 경험", "빌드 시스템 이해", "릴리즈 자동화 경험", "여러 앱 협업 경험"],
        preferred: ["멀티 앱 운영 경험", "보안/권한 체계 경험", "성능 진단 도구 경험"],
        focusAreas: ["공통화", "빌드 안정성", "릴리즈 자동화", "SDK 설계", "운영 효율", "협업 구조"],
        teamCulture: ["재사용 우선", "배포 안정성", "도구화 습관"],
      },
    ],
  },
  {
    id: "devops",
    label: "DevOps/SRE",
    description: "인프라, 배포, 신뢰성 운영을 담당합니다.",
    roles: [
      {
        id: "devops-engineer",
        label: "DevOps 엔지니어",
        description: "CI/CD와 배포 자동화 중심",
        techStack: ["AWS", "Docker", "Kubernetes", "Terraform", "GitHub Actions", "Prometheus"],
        responsibilities: ["CI/CD 파이프라인 운영", "배포 자동화", "인프라 코드 관리", "운영 모니터링 개선"],
        requirements: ["클라우드 운영 경험", "컨테이너 환경 운영 경험", "배포 자동화 경험", "운영 모니터링 경험"],
        preferred: ["IaC 설계 경험", "보안/권한 관리 경험", "멀티 환경 운영 경험"],
        focusAreas: ["배포 자동화", "인프라 코드", "환경 일관성", "운영 협업", "비용 최적화", "관측성"],
        teamCulture: ["자동화 우선", "운영 지표 투명 공유", "사후 회고 문화"],
      },
      {
        id: "devops-sre",
        label: "Site Reliability Engineer",
        description: "가용성과 복구 체계 중심",
        techStack: ["Linux", "Kubernetes", "Grafana", "Prometheus", "Python", "Go"],
        responsibilities: ["SLI/SLO 운영", "장애 탐지/복구 체계 구축", "런북 개선", "리스크 기반 용량 계획"],
        requirements: ["운영 장애 대응 경험", "모니터링 운영 경험", "시스템 성능 분석 경험", "자동화 스크립트 경험"],
        preferred: ["온콜 경험", "분산 시스템 이해", "Chaos Engineering 경험"],
        focusAreas: ["신뢰성 설계", "장애 복구", "모니터링", "용량 계획", "자동화", "운영 커뮤니케이션"],
        teamCulture: ["사실 기반 원인 분석", "재발 방지 우선", "서비스 품질 중심"],
      },
      {
        id: "devops-cloud",
        label: "클라우드 인프라 엔지니어",
        description: "네트워크, 보안, 리소스 운영 중심",
        techStack: ["AWS", "VPC", "IAM", "EKS", "CloudWatch", "Terraform"],
        responsibilities: ["클라우드 아키텍처 운영", "네트워크/권한 정책 설계", "리소스 표준화", "비용 최적화"],
        requirements: ["클라우드 아키텍처 운영 경험", "보안 권한 설계 경험", "네트워크 기본 지식", "문제 해결 경험"],
        preferred: ["멀티 리전 경험", "대규모 마이그레이션 경험", "컴플라이언스 대응 경험"],
        focusAreas: ["클라우드 아키텍처", "권한 관리", "비용 관리", "확장성", "운영 자동화", "리스크 관리"],
        teamCulture: ["표준화와 재사용", "보안 내재화", "협업 중심 운영"],
      },
      {
        id: "devops-platform",
        label: "플랫폼 엔지니어",
        description: "개발자 생산성과 내부 플랫폼 중심",
        techStack: ["Go", "Kubernetes", "Backstage", "Terraform", "Grafana", "GitHub Actions"],
        responsibilities: ["개발자용 플랫폼 구축", "내부 도구 설계", "운영 표준화", "셀프서비스 환경 제공"],
        requirements: ["플랫폼/인프라 개발 경험", "자동화 도구 설계 경험", "여러 팀 협업 경험", "관측성 이해"],
        preferred: ["Internal Developer Platform 경험", "백엔드 개발 경험", "문서 기반 운영 경험"],
        focusAreas: ["개발 생산성", "셀프서비스", "플랫폼 설계", "표준화", "운영 경험", "내부 고객 관점"],
        teamCulture: ["도구화 우선", "재사용 확대", "개발자 경험 중시"],
      },
    ],
  },
  {
    id: "data",
    label: "Data",
    description: "데이터 파이프라인과 분석 기반을 구축합니다.",
    roles: [
      {
        id: "data-engineer",
        label: "데이터 엔지니어",
        description: "수집, 적재, 가공 파이프라인 구축 중심",
        techStack: ["Python", "SQL", "Airflow", "Spark", "BigQuery", "Kafka"],
        responsibilities: ["배치/스트리밍 파이프라인 구축", "데이터 모델링", "품질 검증 체계 운영", "분석/서비스 팀 지원"],
        requirements: ["SQL 숙련", "ETL/ELT 경험", "데이터 품질 관리 경험", "워크플로우 오케스트레이션 경험"],
        preferred: ["실시간 처리 경험", "데이터 거버넌스 경험", "클라우드 데이터 플랫폼 경험"],
        focusAreas: ["파이프라인 설계", "데이터 품질", "모델링", "운영 자동화", "성능 최적화", "협업"],
        teamCulture: ["데이터 신뢰성 우선", "재현 가능한 환경", "문서화 문화"],
      },
      {
        id: "data-analytics",
        label: "애널리틱스 엔지니어",
        description: "지표, 모델, 분석용 데이터셋 설계 중심",
        techStack: ["SQL", "dbt", "BigQuery", "Looker", "Python", "Airflow"],
        responsibilities: ["지표 정의 및 데이터 모델 구축", "분석 파이프라인 개선", "비즈니스 질문 대응", "지표 정확도 검증"],
        requirements: ["SQL 기반 분석 경험", "데이터 모델링 경험", "지표 설계 경험", "이해관계자 커뮤니케이션 경험"],
        preferred: ["실험/AB 테스트 경험", "데이터 시각화 경험", "문서 기반 협업 경험"],
        focusAreas: ["지표 설계", "문제 정의", "데이터 모델링", "실험 분석", "커뮤니케이션", "품질 검증"],
        teamCulture: ["비즈니스 맥락 이해", "가설 검증 중심", "투명한 데이터 운영"],
      },
      {
        id: "data-platform",
        label: "데이터 플랫폼 엔지니어",
        description: "데이터 인프라와 처리 플랫폼 운영 중심",
        techStack: ["Kafka", "Spark", "Kubernetes", "Python", "Terraform", "AWS"],
        responsibilities: ["데이터 플랫폼 구축", "처리 성능 개선", "운영 표준화", "개발자 생산성 도구 제공"],
        requirements: ["분산 처리 시스템 이해", "플랫폼 운영 경험", "자동화 경험", "모니터링 경험"],
        preferred: ["내부 플랫폼 제품화 경험", "대규모 운영 경험", "보안/권한 체계 경험"],
        focusAreas: ["플랫폼 설계", "운영 자동화", "관측성", "성능 튜닝", "표준화", "신뢰성"],
        teamCulture: ["플랫폼 사용자 중심", "운영 효율 극대화", "지속 가능한 개선"],
      },
      {
        id: "data-bi",
        label: "BI/리포팅 엔지니어",
        description: "리포트, 대시보드, 의사결정 지원 환경 중심",
        techStack: ["SQL", "Looker", "Tableau", "dbt", "Python", "BigQuery"],
        responsibilities: ["대시보드/리포트 설계", "지표 품질 관리", "이해관계자 요구사항 정리", "분석 환경 고도화"],
        requirements: ["BI 도구 활용 경험", "지표 설계 경험", "요구사항 분석 경험", "데이터 검증 경험"],
        preferred: ["경영/사업 지표 운영 경험", "데이터 카탈로그 경험", "문서화 경험"],
        focusAreas: ["정보 구조", "지표 해석", "대시보드 설계", "요구사항 정리", "정확성", "커뮤니케이션"],
        teamCulture: ["명확한 정보 전달", "의사결정 지원", "신뢰할 수 있는 리포트"],
      },
    ],
  },
  {
    id: "ai",
    label: "AI/ML",
    description: "모델 개발, 평가, 서빙, LLM 응용을 다룹니다.",
    roles: [
      {
        id: "ai-ml",
        label: "ML 엔지니어",
        description: "모델 학습, 평가, 배포 중심",
        techStack: ["Python", "PyTorch", "TensorFlow", "MLflow", "Docker", "Kubernetes"],
        responsibilities: ["학습 파이프라인 구축", "모델 성능 개선", "평가 지표 정의", "서빙 시스템 운영"],
        requirements: ["모델 학습/평가 경험", "Python 실무 경험", "데이터 전처리 경험", "실험 재현성 관리 경험"],
        preferred: ["온라인 서빙 경험", "MLOps 경험", "대규모 데이터 처리 경험"],
        focusAreas: ["모델 성능", "평가 지표", "실험 관리", "배포 안정성", "비용/지연시간", "문제 해결"],
        teamCulture: ["실험 결과 공유", "근거 기반 개선", "운영 가능성 중시"],
      },
      {
        id: "ai-applied",
        label: "응용 AI 엔지니어",
        description: "제품에 AI 기능을 녹여내는 응용 중심",
        techStack: ["Python", "TypeScript", "FastAPI", "LLM API", "Vector DB", "Redis"],
        responsibilities: ["AI 기능 제품화", "실험 결과를 서비스로 연결", "품질/비용 균형 조정", "운영 문제 대응"],
        requirements: ["AI 기능 개발 경험", "백엔드 또는 프론트엔드 협업 경험", "실험/평가 경험", "제품 관점 문제 해결 경험"],
        preferred: ["검색/추천 경험", "사용자 피드백 기반 개선 경험", "지표 설계 경험"],
        focusAreas: ["제품 적용", "평가 기준", "성능/비용 균형", "실험 반복", "운영 대응", "문제 정의"],
        teamCulture: ["실험과 제품 연결", "작은 검증의 반복", "사용자 가치 우선"],
      },
      {
        id: "ai-llm-app",
        label: "LLM 애플리케이션 엔지니어",
        description: "RAG, 에이전트, 안전성 운영 중심",
        techStack: ["Python", "TypeScript", "LLM API", "Vector DB", "FastAPI", "Redis"],
        responsibilities: ["프롬프트/체인 설계", "RAG 품질 개선", "응답 비용 및 지연시간 최적화", "안전성 가드레일 구축"],
        requirements: ["LLM 앱 개발 경험", "검색/랭킹 기본 이해", "백엔드 API 개발 경험", "실험/평가 경험"],
        preferred: ["에이전트 워크플로우 경험", "멀티모달 처리 경험", "품질 모니터링 체계 경험"],
        focusAreas: ["RAG 품질", "프롬프트 전략", "평가/모니터링", "비용 최적화", "안전성", "운영 신뢰성"],
        teamCulture: ["빠른 실험과 검증", "사용자 피드백 반영", "품질 지표 중심"],
      },
      {
        id: "ai-mlops",
        label: "MLOps 엔지니어",
        description: "ML 시스템 운영과 자동화 중심",
        techStack: ["Python", "Kubernetes", "Airflow", "MLflow", "Terraform", "Prometheus"],
        responsibilities: ["학습/배포 자동화", "모델 버전 관리", "모니터링 체계 구축", "실험-운영 연결 고도화"],
        requirements: ["ML 파이프라인 운영 경험", "클라우드/컨테이너 경험", "관측성 경험", "자동화 스크립트 경험"],
        preferred: ["플랫폼화 경험", "모델 드리프트 대응 경험", "보안/권한 설계 경험"],
        focusAreas: ["파이프라인 자동화", "모델 운영", "관측성", "신뢰성", "비용 효율", "협업"],
        teamCulture: ["운영 자동화", "재현성 우선", "엔지니어링 품질 중시"],
      },
    ],
  },
  {
    id: "security",
    label: "Security",
    description: "애플리케이션과 인프라 보안을 담당합니다.",
    roles: [
      {
        id: "security-engineer",
        label: "보안 엔지니어",
        description: "운영 전반의 보안 설계와 대응 중심",
        techStack: ["SIEM", "WAF", "IAM", "Python", "Linux", "Cloud"],
        responsibilities: ["보안 정책 운영", "위험 식별 및 개선", "탐지 체계 보강", "사고 대응 프로세스 정비"],
        requirements: ["보안 운영 경험", "로그 분석 경험", "네트워크/시스템 기본 이해", "문서화 역량"],
        preferred: ["클라우드 보안 경험", "자동화 스크립트 경험", "침해 대응 경험"],
        focusAreas: ["위험 식별", "탐지/대응", "정책 운영", "로그 분석", "자동화", "커뮤니케이션"],
        teamCulture: ["예방 우선", "정확한 보고", "지식 공유"],
      },
      {
        id: "security-appsec",
        label: "Application Security 엔지니어",
        description: "개발 단계 보안 내재화 중심",
        techStack: ["OWASP", "SAST", "DAST", "Burp Suite", "Python", "CI/CD"],
        responsibilities: ["취약점 진단 및 개선", "보안 코딩 가이드 정립", "개발 파이프라인 보안 점검", "이슈 재발 방지"],
        requirements: ["웹/앱 취약점 이해", "보안 테스트 경험", "개발 협업 경험", "리포팅 경험"],
        preferred: ["DevSecOps 경험", "보안 자동화 경험", "침해 사례 대응 경험"],
        focusAreas: ["취약점 분석", "보안 설계", "개발 보안", "위험도 판단", "자동화", "협업"],
        teamCulture: ["예방 중심 보안", "명확한 리스크 커뮤니케이션", "지속 개선"],
      },
      {
        id: "security-cloud",
        label: "Cloud Security 엔지니어",
        description: "클라우드 환경 보안 아키텍처 중심",
        techStack: ["AWS IAM", "KMS", "WAF", "SIEM", "Terraform", "Kubernetes"],
        responsibilities: ["권한/비밀 관리", "보안 정책 자동화", "침해 탐지 체계 개선", "감사 대응"],
        requirements: ["클라우드 보안 운영 경험", "접근제어 모델 이해", "로그 분석 경험", "사고 대응 경험"],
        preferred: ["컴플라이언스 경험", "대규모 운영 경험", "보안 자동화 경험"],
        focusAreas: ["권한 관리", "탐지/대응", "정책 자동화", "보안 모니터링", "위협 모델링", "거버넌스"],
        teamCulture: ["최소 권한 원칙", "사전 탐지 강화", "운영팀 협업"],
      },
      {
        id: "security-analyst",
        label: "보안 분석가",
        description: "이상 징후 탐지와 초동 대응 중심",
        techStack: ["SIEM", "EDR", "Network", "Linux", "Python", "Threat Intelligence"],
        responsibilities: ["보안 이벤트 모니터링", "침해 지표 분석", "초동 대응 및 에스컬레이션", "사후 분석 리포트 작성"],
        requirements: ["보안 로그 분석 경험", "네트워크/시스템 기본 이해", "사고 대응 프로세스 이해", "문서화 역량"],
        preferred: ["자동화 스크립트 경험", "침해 대응 훈련 경험", "클라우드 보안 경험"],
        focusAreas: ["이벤트 분석", "탐지 룰 개선", "사고 대응", "원인 분석", "자동화", "커뮤니케이션"],
        teamCulture: ["빠른 탐지와 대응", "정확한 보고", "지식 공유"],
      },
    ],
  },
  {
    id: "qa",
    label: "QA/Automation",
    description: "품질 기준을 정의하고 테스트를 자동화합니다.",
    roles: [
      {
        id: "qa-engineer",
        label: "QA 엔지니어",
        description: "테스트 전략과 품질 기준 수립 중심",
        techStack: ["TestRail", "Postman", "SQL", "Jira", "Cypress", "Python"],
        responsibilities: ["테스트 케이스 설계", "회귀 테스트 운영", "결함 분석 및 재현", "품질 리포트 제공"],
        requirements: ["웹/앱 테스트 경험", "결함 관리 경험", "요구사항 분석 능력", "협업 커뮤니케이션 역량"],
        preferred: ["자동화 테스트 경험", "API 테스트 경험", "성능 테스트 경험"],
        focusAreas: ["테스트 설계", "결함 분석", "품질 지표", "회귀 방지", "요구사항 해석", "협업"],
        teamCulture: ["품질 기준 명확화", "조기 검증", "재현성 중심"],
      },
      {
        id: "qa-sdet",
        label: "SDET",
        description: "개발 기반 테스트 프레임워크 중심",
        techStack: ["Java", "TypeScript", "Playwright", "Selenium", "Jest", "CI/CD"],
        responsibilities: ["자동화 테스트 프레임워크 구축", "테스트 파이프라인 운영", "테스트 코드 품질 관리", "릴리즈 게이트 관리"],
        requirements: ["프로그래밍 기반 테스트 경험", "E2E/API 자동화 경험", "CI 연동 경험", "디버깅 역량"],
        preferred: ["테스트 아키텍처 설계 경험", "병렬 테스트 운영 경험", "성능 테스트 경험"],
        focusAreas: ["테스트 자동화", "프레임워크 설계", "CI 품질 게이트", "안정성", "디버깅", "협업"],
        teamCulture: ["자동화 우선", "회귀 최소화", "개발팀과 긴밀 협업"],
      },
      {
        id: "qa-automation",
        label: "테스트 자동화 엔지니어",
        description: "핵심 시나리오 자동화와 운영 중심",
        techStack: ["Python", "Playwright", "Cypress", "GitHub Actions", "Docker", "Allure"],
        responsibilities: ["핵심 시나리오 자동화", "테스트 리포팅 체계 구축", "불안정 테스트 개선", "배포 전 품질 검증"],
        requirements: ["자동화 스크립트 개발 경험", "테스트 시나리오 설계 경험", "CI/CD 연동 경험", "문제 재현 및 분석 역량"],
        preferred: ["테스트 데이터 관리 경험", "성능/보안 테스트 경험", "클라우드 환경 테스트 경험"],
        focusAreas: ["시나리오 자동화", "리포팅", "플레이크 테스트 개선", "품질 기준", "배포 안정성", "운영 효율"],
        teamCulture: ["지속 가능한 테스트", "명확한 품질 신호", "운영 친화적 자동화"],
      },
      {
        id: "qa-platform",
        label: "품질 플랫폼 엔지니어",
        description: "테스트 도구와 품질 인프라 구축 중심",
        techStack: ["TypeScript", "Python", "Playwright", "CI/CD", "Docker", "Observability"],
        responsibilities: ["공통 테스트 도구 제공", "품질 데이터 수집 체계 구축", "릴리즈 품질 게이트 운영", "자동화 플랫폼 개선"],
        requirements: ["자동화 도구 개발 경험", "품질 메트릭 설계 경험", "CI/CD 운영 경험", "여러 팀 협업 경험"],
        preferred: ["내부 플랫폼 경험", "데이터 리포팅 경험", "테스트 프레임워크 설계 경험"],
        focusAreas: ["품질 인프라", "도구화", "메트릭 수집", "게이트 운영", "표준화", "내부 고객 지원"],
        teamCulture: ["도구로 해결", "측정 가능한 품질", "재사용 가능한 자동화"],
      },
    ],
  },
];

export function getRoleCategoryById(id: string | undefined): RoleCategoryTemplate | undefined {
  if (!id) return undefined;
  return ROLE_TRACK_CATEGORIES.find((category) => category.id === id);
}

export function findRoleTemplateByLabel(
  roleLabel: string | undefined,
): { category: RoleCategoryTemplate; role: RoleTemplate } | undefined {
  if (!roleLabel) return undefined;
  for (const category of ROLE_TRACK_CATEGORIES) {
    const role = category.roles.find((item) => item.label === roleLabel);
    if (role) {
      return { category, role };
    }
  }
  return undefined;
}
