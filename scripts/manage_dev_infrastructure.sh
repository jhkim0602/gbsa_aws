#!/usr/bin/env bash

set -euo pipefail

OPERATION="${1:-}"
CONFIRM_DESTROY="${2:-}"
REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_ROOT="$REPOSITORY_ROOT/infra/environments/dev"
FOUNDATION_ROOT="$DEV_ROOT/foundation"
DATA_AI_ROOT="$DEV_ROOT/data-ai"
APPLICATION_ROOT="$DEV_ROOT/application"
COMMON_VARS="$DEV_ROOT/terraform.tfvars.json"
PLAN_DIRECTORY="${RUNNER_TEMP:-/tmp}/iep-dev-plans-${GITHUB_RUN_ID:-local}"
NAME="iep-dev"

: "${AWS_REGION:=ap-northeast-2}"
: "${TERRAFORM_STATE_BUCKET:?TERRAFORM_STATE_BUCKET is required}"

mkdir -p "$PLAN_DIRECTORY"
cd "$REPOSITORY_ROOT"

terraform_init() {
  local root="$1"
  terraform -chdir="$root" init -input=false -reconfigure \
    -backend-config="bucket=$TERRAFORM_STATE_BUCKET" \
    -backend-config="region=$AWS_REGION"
}

terraform_plan_apply() {
  local root="$1"
  local plan_name="$2"
  shift 2
  local plan_path="$PLAN_DIRECTORY/$plan_name.tfplan"

  terraform -chdir="$root" plan -input=false \
    -var-file="$COMMON_VARS" \
    -out="$plan_path" \
    "$@"
  terraform -chdir="$root" apply -input=false "$plan_path"
}

terraform_destroy_if_present() {
  local root="$1"
  local label="$2"
  local resources

  terraform_init "$root"
  resources="$(terraform -chdir="$root" state list 2>/dev/null || true)"
  if [[ -z "$resources" ]]; then
    echo "$label state is already empty; skipping."
    return
  fi

  terraform -chdir="$root" destroy -input=false -auto-approve \
    -var-file="$COMMON_VARS"
}

validate_runtime_secret() {
  local secret_json
  secret_json="$(aws secretsmanager get-secret-value \
    --secret-id "$NAME/application/config" \
    --query SecretString \
    --output text)"
  jq -e '
    (.github_token | type == "string" and length > 0) and
    (.gcp_project_id | type == "string" and length > 0) and
    (.gcp_document_ai_processor_id | type == "string" and length > 0) and
    (.gcp_service_account_json | fromjson | type == "object")
  ' >/dev/null <<<"$secret_json"
}

build_and_push_images() {
  local account_id registry image_tag
  account_id="$(aws sts get-caller-identity --query Account --output text)"
  registry="$account_id.dkr.ecr.$AWS_REGION.amazonaws.com"
  image_tag="${GITHUB_SHA:-local}"
  image_tag="${image_tag:0:12}-${GITHUB_RUN_ID:-0}-${GITHUB_RUN_ATTEMPT:-1}"
  API_IMAGE="$registry/$NAME/api:$image_tag"
  WORKER_IMAGE="$registry/$NAME/worker:$image_tag"
  export API_IMAGE WORKER_IMAGE

  aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
  docker build --platform linux/amd64 --target api --tag "$API_IMAGE" --file backend/Containerfile .
  docker build --platform linux/amd64 --target worker --tag "$WORKER_IMAGE" --file backend/Containerfile .
  docker push "$API_IMAGE"
  docker push "$WORKER_IMAGE"
}

run_database_migration() {
  local network_configuration overrides task_arn exit_code
  network_configuration="$(aws ecs describe-services \
    --cluster "$NAME" \
    --services "$NAME-worker" \
    --query 'services[0].networkConfiguration' \
    --output json)"
  overrides="$(jq -nc '{
    containerOverrides: [{
      name: "worker",
      command: [
        "uv", "run", "--no-sync", "python",
        "-m", "interview_evidence.migrate"
      ]
    }]
  }')"
  task_arn="$(aws ecs run-task \
    --cluster "$NAME" \
    --launch-type FARGATE \
    --task-definition "$NAME-worker" \
    --network-configuration "$network_configuration" \
    --overrides "$overrides" \
    --query 'tasks[0].taskArn' \
    --output text)"
  [[ "$task_arn" != "None" ]]
  aws ecs wait tasks-stopped --cluster "$NAME" --tasks "$task_arn"
  exit_code="$(aws ecs describe-tasks \
    --cluster "$NAME" \
    --tasks "$task_arn" \
    --query 'tasks[0].containers[?name==`worker`].exitCode | [0]' \
    --output text)"
  [[ "$exit_code" == "0" ]]
}

publish_frontends() {
  local frontend company_bucket applicant_bucket company_distribution applicant_distribution
  local company_url applicant_url cognito_domain cognito_client_id cognito_redirect_uri
  local demo_company_email demo_company_token
  local company_invalidation applicant_invalidation

  frontend="$(terraform -chdir="$APPLICATION_ROOT" output -json frontend)"
  company_bucket="$(jq -er '.sites.company.bucket' <<<"$frontend")"
  applicant_bucket="$(jq -er '.sites.applicant.bucket' <<<"$frontend")"
  company_distribution="$(jq -er '.sites.company.distribution_id' <<<"$frontend")"
  applicant_distribution="$(jq -er '.sites.applicant.distribution_id' <<<"$frontend")"
  company_url="$(jq -er '.sites.company.url' <<<"$frontend")"
  applicant_url="$(jq -er '.sites.applicant.url' <<<"$frontend")"
  cognito_domain="$(jq -er '.cognito.login_domain' <<<"$frontend")"
  cognito_client_id="$(jq -er '.cognito.client_id' <<<"$frontend")"
  cognito_redirect_uri="$(jq -er '.cognito.redirect_uri' <<<"$frontend")"
  demo_company_email="$(jq -er '.demo.email' <<<"$frontend")"
  demo_company_token="$(jq -er '.demo.access_token' <<<"$frontend")"

  VITE_API_BASE_URL="" \
  VITE_APPLICANT_APP_URL="$applicant_url/access" \
  VITE_COGNITO_DOMAIN="$cognito_domain" \
  VITE_COGNITO_CLIENT_ID="$cognito_client_id" \
  VITE_COGNITO_REDIRECT_URI="$cognito_redirect_uri" \
  VITE_AUTOMATED_INTERVIEW_ENABLED="true" \
  VITE_DEMO_COMPANY_EMAIL="$demo_company_email" \
  VITE_DEMO_COMPANY_TOKEN="$demo_company_token" \
    npm run build

  aws s3 cp apps/company-console/dist "s3://$company_bucket" --recursive
  aws s3 sync apps/company-console/dist "s3://$company_bucket" --delete
  aws s3 cp apps/applicant-interview/dist "s3://$applicant_bucket" --recursive
  aws s3 sync apps/applicant-interview/dist "s3://$applicant_bucket" --delete
  company_invalidation="$(aws cloudfront create-invalidation \
    --distribution-id "$company_distribution" \
    --paths '/*' \
    --query 'Invalidation.Id' \
    --output text)"
  applicant_invalidation="$(aws cloudfront create-invalidation \
    --distribution-id "$applicant_distribution" \
    --paths '/*' \
    --query 'Invalidation.Id' \
    --output text)"
  aws cloudfront wait invalidation-completed \
    --distribution-id "$company_distribution" \
    --id "$company_invalidation"
  aws cloudfront wait invalidation-completed \
    --distribution-id "$applicant_distribution" \
    --id "$applicant_invalidation"

  COMPANY_URL="$company_url" \
  APPLICANT_URL="$applicant_url" \
    scripts/smoke_deployed.sh

  {
    echo "### Development environment"
    echo "- Company console: $company_url"
    echo "- Applicant interview: $applicant_url/access"
  } >>"${GITHUB_STEP_SUMMARY:-/dev/null}"
}

bring_up() {
  local callback_vars company_url existing_application_state frontend
  local -a foundation_overrides=()

  validate_runtime_secret

  terraform_init "$APPLICATION_ROOT"
  existing_application_state="$(
    terraform -chdir="$APPLICATION_ROOT" state list 2>/dev/null || true
  )"
  if [[ -n "$existing_application_state" ]]; then
    frontend="$(terraform -chdir="$APPLICATION_ROOT" output -json frontend)"
    company_url="$(jq -er '.sites.company.url' <<<"$frontend")"
    callback_vars="$PLAN_DIRECTORY/foundation-callbacks.tfvars.json"
    jq -n --arg company_url "$company_url" '{
      console_base_urls: ["http://localhost:5173", $company_url]
    }' >"$callback_vars"
    foundation_overrides=(-var-file="$callback_vars")
  fi

  terraform_init "$FOUNDATION_ROOT"
  if ((${#foundation_overrides[@]})); then
    terraform_plan_apply "$FOUNDATION_ROOT" foundation "${foundation_overrides[@]}"
  else
    terraform_plan_apply "$FOUNDATION_ROOT" foundation
  fi

  terraform_init "$DATA_AI_ROOT"
  terraform_plan_apply "$DATA_AI_ROOT" data-ai

  terraform_plan_apply "$APPLICATION_ROOT" registries \
    -target=module.compute.aws_ecr_repository.api \
    -target=module.compute.aws_ecr_repository.worker
  build_and_push_images
  terraform_plan_apply "$APPLICATION_ROOT" application \
    -var="api_image=$API_IMAGE" \
    -var="worker_image=$WORKER_IMAGE"

  frontend="$(terraform -chdir="$APPLICATION_ROOT" output -json frontend)"
  company_url="$(jq -er '.sites.company.url' <<<"$frontend")"
  callback_vars="$PLAN_DIRECTORY/foundation-callbacks.tfvars.json"
  jq -n --arg company_url "$company_url" '{
    console_base_urls: ["http://localhost:5173", $company_url]
  }' >"$callback_vars"
  terraform_plan_apply "$FOUNDATION_ROOT" foundation-callbacks \
    -var-file="$callback_vars"

  aws ecs update-service \
    --cluster "$NAME" \
    --service "$NAME-api" \
    --task-definition "$NAME-api" \
    --force-new-deployment >/dev/null
  aws ecs update-service \
    --cluster "$NAME" \
    --service "$NAME-worker" \
    --task-definition "$NAME-worker" \
    --force-new-deployment >/dev/null
  aws ecs wait services-stable \
    --cluster "$NAME" \
    --services "$NAME-api" "$NAME-worker"

  run_database_migration
  npm ci
  publish_frontends

  local sender_address verification_status
  sender_address="$(jq -r '.sender_address' "$COMMON_VARS")"
  verification_status="$(aws sesv2 get-email-identity \
    --email-identity "$sender_address" \
    --query VerifiedForSendingStatus \
    --output text 2>/dev/null || echo false)"
  if [[ "$verification_status" != "True" && "$verification_status" != "true" ]]; then
    echo "::warning::Open the SES verification email sent to $sender_address before testing invitations."
  fi
}

tear_down() {
  if [[ "$CONFIRM_DESTROY" != "destroy-dev" ]]; then
    echo "::error::Enter destroy-dev in the confirmation field."
    exit 1
  fi

  terraform_destroy_if_present "$APPLICATION_ROOT" application
  terraform_destroy_if_present "$DATA_AI_ROOT" data-ai
  terraform_destroy_if_present "$FOUNDATION_ROOT" foundation

  {
    echo "### Development environment removed"
    echo "The Terraform state bucket and GitHub deployment role were retained."
  } >>"${GITHUB_STEP_SUMMARY:-/dev/null}"
}

case "$OPERATION" in
  up)
    bring_up
    ;;
  down)
    tear_down
    ;;
  *)
    echo "usage: $0 <up|down> [destroy-dev]" >&2
    exit 2
    ;;
esac
