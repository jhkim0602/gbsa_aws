export const DEFAULT_TECH_LOGO_BASE_PATH = "/tech-stack-combobox/logos";

export interface TechLogoMeta {
  src: string;
  label: string;
}

interface TechLogoDefinition {
  file: string;
  label: string;
}

const TECH_LOGO_BY_KEY: Record<string, TechLogoDefinition> = {
  airflow: { file: "airflow.svg", label: "Airflow" },
  android: { file: "android.svg", label: "Android" },
  apacheairflow: { file: "airflow.svg", label: "Airflow" },
  apachekafka: { file: "kafka.svg", label: "Kafka" },
  apachespark: { file: "spark.svg", label: "Spark" },
  aws: { file: "aws.svg", label: "AWS" },
  awsiam: { file: "aws.svg", label: "AWS IAM" },
  backstage: { file: "backstage.svg", label: "Backstage" },
  bigquery: { file: "bigquery.svg", label: "BigQuery" },
  burpsuite: { file: "burp-suite.svg", label: "Burp Suite" },
  canvas: { file: "html5.svg", label: "Canvas" },
  chart: { file: "chartjs.svg", label: "Chart.js" },
  chartjs: { file: "chartjs.svg", label: "Chart.js" },
  cicd: { file: "github-actions.svg", label: "CI/CD" },
  cloud: { file: "cloud.svg", label: "Cloud" },
  cloudwatch: { file: "aws.svg", label: "CloudWatch" },
  css: { file: "css.svg", label: "CSS" },
  css3: { file: "css.svg", label: "CSS" },
  cypress: { file: "cypress.svg", label: "Cypress" },
  dart: { file: "dart.svg", label: "Dart" },
  dask: { file: "python.svg", label: "Python" },
  dast: { file: "owasp.svg", label: "DAST" },
  docker: { file: "docker.svg", label: "Docker" },
  eks: { file: "kubernetes.svg", label: "EKS" },
  elastic: { file: "elastic.svg", label: "Elastic" },
  edr: { file: "elastic.svg", label: "EDR" },
  fastapi: { file: "fastapi.svg", label: "FastAPI" },
  fastlane: { file: "fastlane.svg", label: "Fastlane" },
  figma: { file: "figma.svg", label: "Figma" },
  firebase: { file: "firebase.svg", label: "Firebase" },
  flutter: { file: "flutter.svg", label: "Flutter" },
  framer: { file: "motion.svg", label: "Motion" },
  framermotion: { file: "motion.svg", label: "Motion" },
  githubactions: { file: "github-actions.svg", label: "GitHub Actions" },
  go: { file: "go.svg", label: "Go" },
  golang: { file: "go.svg", label: "Go" },
  googlebigquery: { file: "bigquery.svg", label: "BigQuery" },
  gradle: { file: "gradle.svg", label: "Gradle" },
  grafana: { file: "grafana.svg", label: "Grafana" },
  iam: { file: "aws.svg", label: "IAM" },
  ios: { file: "ios.svg", label: "iOS" },
  java: { file: "java.svg", label: "Java" },
  jest: { file: "jest.svg", label: "Jest" },
  jetpack: { file: "jetpack.svg", label: "Jetpack" },
  jira: { file: "jira.svg", label: "Jira" },
  kafka: { file: "kafka.svg", label: "Kafka" },
  kms: { file: "aws.svg", label: "KMS" },
  kotlin: { file: "kotlin.svg", label: "Kotlin" },
  kubernetes: { file: "kubernetes.svg", label: "Kubernetes" },
  k8s: { file: "kubernetes.svg", label: "Kubernetes" },
  linux: { file: "linux.svg", label: "Linux" },
  looker: { file: "looker.svg", label: "Looker" },
  mlflow: { file: "mlflow.svg", label: "MLflow" },
  motion: { file: "motion.svg", label: "Motion" },
  mysql: { file: "mysql.svg", label: "MySQL" },
  network: { file: "cloud.svg", label: "Network" },
  next: { file: "nextjs.svg", label: "Next.js" },
  nextjs: { file: "nextjs.svg", label: "Next.js" },
  node: { file: "nodejs.svg", label: "Node.js" },
  nodejs: { file: "nodejs.svg", label: "Node.js" },
  observability: { file: "grafana.svg", label: "Observability" },
  openjdk: { file: "java.svg", label: "Java" },
  owasp: { file: "owasp.svg", label: "OWASP" },
  playwright: { file: "playwright.svg", label: "Playwright" },
  postgresql: { file: "postgresql.svg", label: "PostgreSQL" },
  postgres: { file: "postgresql.svg", label: "PostgreSQL" },
  postman: { file: "postman.svg", label: "Postman" },
  prometheus: { file: "prometheus.svg", label: "Prometheus" },
  python: { file: "python.svg", label: "Python" },
  pytorch: { file: "pytorch.svg", label: "PyTorch" },
  pytest: { file: "pytest.svg", label: "Pytest" },
  react: { file: "react.svg", label: "React" },
  reactnative: { file: "react.svg", label: "React Native" },
  reactquery: { file: "tanstack.svg", label: "TanStack Query" },
  redis: { file: "redis.svg", label: "Redis" },
  room: { file: "android.svg", label: "Room" },
  sast: { file: "owasp.svg", label: "SAST" },
  selenium: { file: "selenium.svg", label: "Selenium" },
  siem: { file: "elastic.svg", label: "SIEM" },
  spark: { file: "spark.svg", label: "Spark" },
  spring: { file: "spring.svg", label: "Spring" },
  springboot: { file: "spring-boot.svg", label: "Spring Boot" },
  sql: { file: "sql.svg", label: "SQL" },
  storybook: { file: "storybook.svg", label: "Storybook" },
  swift: { file: "swift.svg", label: "Swift" },
  swiftui: { file: "swift.svg", label: "SwiftUI" },
  table: { file: "chartjs.svg", label: "Table" },
  tanstack: { file: "tanstack.svg", label: "TanStack" },
  tanstackquery: { file: "tanstack.svg", label: "TanStack Query" },
  tensorflow: { file: "tensorflow.svg", label: "TensorFlow" },
  terraform: { file: "terraform.svg", label: "Terraform" },
  threatintelligence: { file: "owasp.svg", label: "Threat Intelligence" },
  ts: { file: "typescript.svg", label: "TypeScript" },
  typescript: { file: "typescript.svg", label: "TypeScript" },
  uikit: { file: "ios.svg", label: "UIKit" },
  vector: { file: "elastic.svg", label: "Vector DB" },
  vectordb: { file: "elastic.svg", label: "Vector DB" },
  vite: { file: "vite.svg", label: "Vite" },
  vpc: { file: "aws.svg", label: "VPC" },
  waf: { file: "cloudflare.svg", label: "WAF" },
};

function normalizeTechKey(label: string) {
  return label
    .trim()
    .toLowerCase()
    .replace(/\+/g, "plus")
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]/g, "");
}

function createLogoMeta(
  definition: TechLogoDefinition,
  basePath: string,
): TechLogoMeta {
  return {
    src: `${basePath.replace(/\/$/, "")}/${definition.file}`,
    label: definition.label,
  };
}

export function getTechLogo(
  label: string,
  basePath = DEFAULT_TECH_LOGO_BASE_PATH,
): TechLogoMeta | null {
  const definition = TECH_LOGO_BY_KEY[normalizeTechKey(label)];
  return definition ? createLogoMeta(definition, basePath) : null;
}

/**
 * 사전(`TECH_LOGO_BY_KEY`)에 등록된 모든 기술의 distinct label 목록을 반환한다.
 * - 동일 label에 대한 alias 키(예: `next`, `nextjs` → "Next.js")는 한 번만 포함된다.
 * - 결과는 라벨 알파벳 오름차순으로 정렬된다.
 */
export function getAllTechLabels(
  basePath = DEFAULT_TECH_LOGO_BASE_PATH,
): TechLogoMeta[] {
  const seen = new Map<string, TechLogoDefinition>();
  for (const definition of Object.values(TECH_LOGO_BY_KEY)) {
    if (!seen.has(definition.label)) {
      seen.set(definition.label, definition);
    }
  }
  return Array.from(seen.values())
    .map((definition) => createLogoMeta(definition, basePath))
    .sort((a, b) =>
      a.label.localeCompare(b.label, "en", { sensitivity: "base" }),
    );
}
