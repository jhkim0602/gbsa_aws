#!/usr/bin/env bash
# Writes the company principal a Cognito user signs in as, in the deployed environment.
#
# Creating the pool user is not enough on its own: `get_company_principal` reads
# `custom:company_id` and `custom:company_user_id` from the token and then looks the caller up
# by `identity_subject`, which is the pool's `sub`. Without matching rows the login succeeds and
# every request afterwards answers 401, which reads as a broken token rather than a missing row.
#
# Run from a workstation; the task itself runs in the private subnets, which is the only place
# the database is reachable from. No DATABASE_URL is passed -- the seed resolves Aurora from
# Secrets Manager inside the container, so the password stays out of this override, out of the
# task description and out of the CloudTrail event.
#
# Every identifying value comes from the environment, because this file is committed and a
# repository can be public:
#
#   LOCAL_COMPANY_ID=... LOCAL_COMPANY_USER_ID=... LOCAL_COMPANY_IDENTITY_SUBJECT=... \
#   LOCAL_COMPANY_EMAIL=... LOCAL_COMPANY_NAME=... ./scripts/seed_dev_principal.sh
#
# Read the subject and the two ids back from the pool with:
#   aws cognito-idp admin-get-user --user-pool-id "$POOL" --username "$EMAIL" \
#     --query 'UserAttributes[?Name==`sub`||starts_with(Name,`custom:`)]'
set -euo pipefail

CLUSTER="${CLUSTER:-iep-dev}"
REGION="${AWS_REGION:-ap-northeast-2}"
DEMO_DATA="${LOCAL_DEMO_DATA_ENABLED:-true}"

for name in LOCAL_COMPANY_ID LOCAL_COMPANY_USER_ID LOCAL_COMPANY_IDENTITY_SUBJECT \
  LOCAL_COMPANY_EMAIL LOCAL_COMPANY_NAME; do
  if [[ -z "${!name:-}" ]]; then
    echo "required setting is missing: $name" >&2
    exit 1
  fi
done

# Copied from the running service rather than written out here, so the task lands in the same
# subnets and security group the worker already uses to reach Aurora.
NETWORK="$(aws ecs describe-services \
  --cluster "$CLUSTER" \
  --services "$CLUSTER-worker" \
  --region "$REGION" \
  --query 'services[0].networkConfiguration' \
  --output json)"

OVERRIDES="$(jq -nc \
  --arg company_id "$LOCAL_COMPANY_ID" \
  --arg company_user_id "$LOCAL_COMPANY_USER_ID" \
  --arg identity_subject "$LOCAL_COMPANY_IDENTITY_SUBJECT" \
  --arg email "$LOCAL_COMPANY_EMAIL" \
  --arg company_name "$LOCAL_COMPANY_NAME" \
  --arg demo_data "$DEMO_DATA" \
  '{
    containerOverrides: [{
      name: "worker",
      command: [
        "uv", "run", "--no-sync", "python",
        "-m", "interview_evidence.runtime.local_seed"
      ],
      environment: [
        {name: "LOCAL_COMPANY_ID", value: $company_id},
        {name: "LOCAL_COMPANY_USER_ID", value: $company_user_id},
        {name: "LOCAL_COMPANY_IDENTITY_SUBJECT", value: $identity_subject},
        {name: "LOCAL_COMPANY_EMAIL", value: $email},
        {name: "LOCAL_COMPANY_NAME", value: $company_name},
        {name: "LOCAL_DEMO_DATA_ENABLED", value: $demo_data}
      ]
    }]
  }')"

TASK_ARN="$(aws ecs run-task \
  --cluster "$CLUSTER" \
  --launch-type FARGATE \
  --task-definition "$CLUSTER-worker" \
  --network-configuration "$NETWORK" \
  --overrides "$OVERRIDES" \
  --region "$REGION" \
  --query 'tasks[0].taskArn' \
  --output text)"
test "$TASK_ARN" != "None"
echo "task: $TASK_ARN"

aws ecs wait tasks-stopped --cluster "$CLUSTER" --tasks "$TASK_ARN" --region "$REGION"
EXIT_CODE="$(aws ecs describe-tasks \
  --cluster "$CLUSTER" \
  --tasks "$TASK_ARN" \
  --region "$REGION" \
  --query 'tasks[0].containers[?name==`worker`].exitCode | [0]' \
  --output text)"
echo "exit code: $EXIT_CODE"
# The seed is idempotent, so rerunning after a failure is safe.
test "$EXIT_CODE" = "0"
echo "seeded"
