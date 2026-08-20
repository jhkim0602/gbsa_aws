/**
 * 기술 스택의 직무별 카테고리 분류.
 *
 * 이력서의 TECHNICAL SKILLS 섹션과 편집기에서 "프론트엔드 / 백엔드 / DevOps · 인프라"
 * 식으로 그룹핑하기 위해 사용한다. 사전(`tech-logos`)에 등록된 라벨 → 카테고리 키로
 * 매핑한다. 사용자가 명시적으로 `skill.category` 를 지정하면 그 값이 우선한다.
 */

export type TechCategoryKey =
  | "frontend"
  | "backend"
  | "mobile"
  | "database"
  | "devops"
  | "data"
  | "security"
  | "testing"
  | "design"
  | "language"
  | "etc";

export interface TechCategoryMeta {
  key: TechCategoryKey;
  label: string;
  hint: string;
  /** 정렬용 가중치. 작을수록 위쪽. */
  order: number;
}

export const TECH_CATEGORIES: Record<TechCategoryKey, TechCategoryMeta> = {
  frontend: {
    key: "frontend",
    label: "프론트엔드",
    hint: "Web UI / 클라이언트",
    order: 1,
  },
  backend: { key: "backend", label: "백엔드", hint: "서버 / API", order: 2 },
  mobile: { key: "mobile", label: "모바일", hint: "iOS · Android", order: 3 },
  database: {
    key: "database",
    label: "데이터베이스",
    hint: "RDB / NoSQL / Cache",
    order: 4,
  },
  devops: {
    key: "devops",
    label: "DevOps · 인프라",
    hint: "배포 / 운영 / 관측",
    order: 5,
  },
  data: {
    key: "data",
    label: "데이터 · AI",
    hint: "ML / 데이터 파이프라인",
    order: 6,
  },
  security: {
    key: "security",
    label: "보안",
    hint: "SAST / DAST / SIEM",
    order: 7,
  },
  testing: {
    key: "testing",
    label: "테스트 · QA",
    hint: "E2E / Unit / 통합",
    order: 8,
  },
  design: {
    key: "design",
    label: "디자인 · 협업",
    hint: "Figma / Jira / 노션",
    order: 9,
  },
  language: {
    key: "language",
    label: "언어",
    hint: "Programming Language",
    order: 10,
  },
  etc: { key: "etc", label: "기타", hint: "분류되지 않은 항목", order: 11 },
};

export const TECH_CATEGORY_LIST: TechCategoryMeta[] = Object.values(
  TECH_CATEGORIES,
).sort((a, b) => a.order - b.order);

/**
 * 카테고리 검색을 위한 한국어/영문 키워드 사전. 사용자가 "프론트엔드"·"frontend"·"front"·
 * "FE" 처럼 다양한 표기를 검색해도 같은 카테고리로 매칭한다.
 */
export const TECH_CATEGORY_SEARCH_KEYWORDS: Record<TechCategoryKey, string[]> =
  {
    frontend: [
      "프론트엔드",
      "프론트",
      "프런트",
      "frontend",
      "front",
      "fe",
      "웹",
    ],
    backend: ["백엔드", "백앤드", "backend", "back", "be", "서버", "api"],
    mobile: [
      "모바일",
      "mobile",
      "앱",
      "ios",
      "android",
      "안드로이드",
      "아이오에스",
    ],
    database: ["데이터베이스", "디비", "database", "db", "rdb", "nosql"],
    devops: [
      "데브옵스",
      "devops",
      "인프라",
      "infra",
      "운영",
      "sre",
      "클라우드",
      "cloud",
      "ops",
    ],
    data: ["데이터", "ai", "ml", "data", "머신러닝", "딥러닝", "인공지능"],
    security: ["보안", "security", "sec", "정보보안", "해킹"],
    testing: ["테스트", "테스팅", "test", "qa", "e2e", "유닛"],
    design: ["디자인", "design", "협업", "ux", "ui"],
    language: ["언어", "language", "프로그래밍 언어", "lang"],
    etc: ["기타", "etc", "other"],
  };

/**
 * 한국어/영문 키워드 → 카테고리 키 역인덱스 (소문자 normalize 적용).
 */
const CATEGORY_KEYWORD_INDEX: Map<string, TechCategoryKey> = new Map();
for (const [key, words] of Object.entries(TECH_CATEGORY_SEARCH_KEYWORDS)) {
  for (const word of words) {
    CATEGORY_KEYWORD_INDEX.set(word.toLowerCase(), key as TechCategoryKey);
  }
  // 카테고리 라벨 자체도 인덱스에 추가
  CATEGORY_KEYWORD_INDEX.set(
    TECH_CATEGORIES[key as TechCategoryKey].label.toLowerCase(),
    key as TechCategoryKey,
  );
}

/**
 * 검색어가 카테고리 키워드와 일치하면 해당 카테고리를 반환. prefix 매칭도 지원.
 * 예: "프론트" → frontend, "back" → backend.
 */
export function matchCategoryByQuery(query: string): TechCategoryKey | null {
  const lower = query.trim().toLowerCase();
  if (!lower) return null;
  // 정확 일치 우선
  const exact = CATEGORY_KEYWORD_INDEX.get(lower);
  if (exact) return exact;
  // prefix 매칭 (입력 중일 때 안 끝까지 입력해도 매칭되도록)
  for (const [keyword, cat] of CATEGORY_KEYWORD_INDEX.entries()) {
    if (keyword.startsWith(lower) || lower.startsWith(keyword)) {
      return cat;
    }
  }
  return null;
}

function normalize(label: string) {
  return label
    .trim()
    .toLowerCase()
    .replace(/\+/g, "plus")
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]/g, "");
}

/**
 * 라벨 normalize → 카테고리 매핑 사전.
 * tech-logos 의 alias 키들과 동일한 normalize 규칙을 사용한다.
 */
const CATEGORY_BY_KEY: Record<string, TechCategoryKey> = {
  // Frontend
  react: "frontend",
  reactnative: "mobile",
  nextjs: "frontend",
  next: "frontend",
  vue: "frontend",
  nuxt: "frontend",
  angular: "frontend",
  svelte: "frontend",
  typescript: "frontend",
  ts: "frontend",
  javascript: "frontend",
  js: "frontend",
  html: "frontend",
  html5: "frontend",
  css: "frontend",
  css3: "frontend",
  tailwind: "frontend",
  tailwindcss: "frontend",
  sass: "frontend",
  scss: "frontend",
  vite: "frontend",
  storybook: "frontend",
  motion: "frontend",
  framer: "frontend",
  framermotion: "frontend",
  tanstack: "frontend",
  tanstackquery: "frontend",
  reactquery: "frontend",
  chartjs: "frontend",
  chart: "frontend",
  canvas: "frontend",
  table: "frontend",

  // Backend
  nodejs: "backend",
  node: "backend",
  express: "backend",
  nestjs: "backend",
  springboot: "backend",
  spring: "backend",
  fastapi: "backend",
  django: "backend",
  flask: "backend",
  rails: "backend",
  laravel: "backend",
  graphql: "backend",
  rest: "backend",
  grpc: "backend",

  // Languages (also classifiable, but keep specific)
  java: "language",
  python: "language",
  go: "language",
  golang: "language",
  kotlin: "language",
  swift: "language",
  rust: "language",
  ruby: "language",
  php: "language",
  cplusplus: "language",
  csharp: "language",
  dart: "language",
  openjdk: "language",

  // Mobile
  android: "mobile",
  ios: "mobile",
  flutter: "mobile",
  swiftui: "mobile",
  uikit: "mobile",
  jetpack: "mobile",
  room: "mobile",
  fastlane: "mobile",

  // Database
  postgresql: "database",
  postgres: "database",
  mysql: "database",
  mariadb: "database",
  oracle: "database",
  mssql: "database",
  mongodb: "database",
  redis: "database",
  bigquery: "database",
  googlebigquery: "database",
  dynamodb: "database",
  cassandra: "database",
  sql: "database",
  sqlite: "database",
  vector: "database",
  vectordb: "database",

  // DevOps / Infra
  docker: "devops",
  kubernetes: "devops",
  k8s: "devops",
  eks: "devops",
  aws: "devops",
  awsiam: "devops",
  iam: "devops",
  kms: "devops",
  vpc: "devops",
  cloudwatch: "devops",
  gcp: "devops",
  azure: "devops",
  terraform: "devops",
  ansible: "devops",
  jenkins: "devops",
  githubactions: "devops",
  cicd: "devops",
  argocd: "devops",
  helm: "devops",
  cloudflare: "devops",
  nginx: "devops",
  apache: "devops",
  linux: "devops",
  prometheus: "devops",
  grafana: "devops",
  elastic: "devops",
  observability: "devops",
  backstage: "devops",
  cloud: "devops",
  network: "devops",

  // Data / AI
  tensorflow: "data",
  pytorch: "data",
  spark: "data",
  apachespark: "data",
  hadoop: "data",
  kafka: "data",
  apachekafka: "data",
  airflow: "data",
  apacheairflow: "data",
  mlflow: "data",
  looker: "data",
  dask: "data",
  pandas: "data",
  numpy: "data",
  sklearn: "data",
  scikitlearn: "data",
  langchain: "data",
  openai: "data",
  gemini: "data",

  // Security
  owasp: "security",
  burpsuite: "security",
  sast: "security",
  dast: "security",
  edr: "security",
  siem: "security",
  waf: "security",
  threatintelligence: "security",

  // Testing / QA
  jest: "testing",
  pytest: "testing",
  cypress: "testing",
  playwright: "testing",
  selenium: "testing",
  vitest: "testing",
  mocha: "testing",
  chai: "testing",
  postman: "testing",

  // Design / Collaboration
  figma: "design",
  sketch: "design",
  jira: "design",
  notion: "design",
  slack: "design",
  miro: "design",

  // Misc
  firebase: "devops",
  gradle: "devops",
};

/**
 * 라벨 → TechCategoryKey 추론. 사전에 없으면 "etc" 반환.
 */
export function getTechCategory(label: string): TechCategoryKey {
  return CATEGORY_BY_KEY[normalize(label)] ?? "etc";
}

/**
 * skills 배열을 카테고리별로 그룹핑. 사용자가 명시적으로 `skill.category` 를 지정한
 * 경우 우선 사용하고, 없으면 라벨 기반 추론.
 *
 * 결과는 TECH_CATEGORY_LIST 의 order 순으로 정렬되며 비어있는 카테고리는 제외된다.
 */
export function groupSkillsByCategory<
  T extends { name: string; category?: string },
>(skills: T[]): Array<{ category: TechCategoryMeta; items: T[] }> {
  const buckets = new Map<TechCategoryKey, T[]>();
  for (const skill of skills) {
    const key: TechCategoryKey =
      (skill.category as TechCategoryKey | undefined) &&
      TECH_CATEGORIES[skill.category as TechCategoryKey]
        ? (skill.category as TechCategoryKey)
        : getTechCategory(skill.name);
    const list = buckets.get(key) ?? [];
    list.push(skill);
    buckets.set(key, list);
  }
  return TECH_CATEGORY_LIST.filter((meta) => buckets.has(meta.key)).map(
    (meta) => ({
      category: meta,
      items: buckets.get(meta.key) ?? [],
    }),
  );
}
