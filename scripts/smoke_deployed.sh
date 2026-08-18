#!/usr/bin/env bash
#
# A handful of checks against a deployed environment, and deliberately only a handful.
#
# The browser suite stays pointed at the local stack, where the seed is deterministic and it
# can assert exact names and counts. This script covers the part the local stack cannot
# reproduce at all: nginx, Mailpit and the fake principal provider stand in for CloudFront,
# SES and Cognito, so every defect that lives in the difference between them is invisible
# locally no matter how thorough the specs are. Each check below corresponds to one such
# defect that was actually found by inspection.
#
# It asserts nothing about application data, which is what keeps it cheap enough to run on
# every deploy: no seeded rows, no login, no mailbox to poll, nothing to clean up afterwards.
#
# Usage: COMPANY_URL=... APPLICANT_URL=... scripts/smoke_deployed.sh
set -euo pipefail

: "${COMPANY_URL:?COMPANY_URL is required}"
: "${APPLICANT_URL:?APPLICANT_URL is required}"

failures=0

# `curl -o /dev/null -w %{http_code}` rather than `-f`: a wrong status is the finding here,
# so the status has to be read and compared, not turned into a non-zero exit.
status_of() {
  curl --silent --show-error --location --max-time 20 \
    --output /dev/null --write-out '%{http_code}' "$1"
}

header_of() {
  curl --silent --show-error --location --max-time 20 \
    --output /dev/null --write-out "%header{$2}" "$1"
}

check() {
  local name="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    echo "ok       $name ($actual)"
  else
    echo "FAILED   $name: expected $expected, got $actual"
    failures=$((failures + 1))
  fi
}

echo "== deployed smoke =="

# 1. Each SPA document is served, and a client-side route resolves to it.
#
# The route matters separately from the root: `/access/<token>` is not a file in the bucket,
# and whether it returns the document depends on the CloudFront function rewriting
# extension-less paths. Without it the applicant follows an invitation link to a 403.
#
# Split on a tab, not a colon: every URL here contains `https://`, so `IFS=:` would leave
# `base` holding the string "https" and send all four checks to an address that resolves to
# nothing -- while still reporting a status and looking like a genuine failure.
while IFS=$'\t' read -r name base route; do
  check "$name document" 200 "$(status_of "$base/")"
  check "$name client route $route" 200 "$(status_of "$base$route")"
done <<EOF
company	$COMPANY_URL	/positions
applicant	$APPLICANT_URL	/access/smoke
EOF

# 2. A missing hashed asset is 404, not the document with status 200.
#
# The defect this pins: S3 answers 403 for an absent key unless the caller also holds
# `s3:ListBucket`, and a `custom_error_response` mapping 403 to `/index.html` therefore
# served HTML in place of JavaScript. A browser holding a cached document that names a
# since-deleted asset then shows a blank page whose only trace is a MIME type error, with
# every health check green. Local nginx hides this behind `try_files $uri =404`.
while IFS=$'\t' read -r name base; do
  check "$name stale asset is not the document" 404 \
    "$(status_of "$base/assets/index-smoke-absent.js")"
done <<EOF
company	$COMPANY_URL
applicant	$APPLICANT_URL
EOF

# 3. The API is reachable through the same origin the SPA was served from, and authenticates.
#
# 401 is the pass condition. It proves the request reached the application rather than the
# SPA bucket -- a 200 here would mean the `/v1/*` behaviour is missing and the document was
# returned instead, and a 403 would mean WAF or the origin policy stopped it before the app.
check "company origin routes /v1 to the API" 401 "$(status_of "$COMPANY_URL/v1/me")"

# No separate `/health/ready` check, and the reason is a constraint rather than an omission.
#
# The ALB security group admits CloudFront's managed prefix list only, so neither CI nor a
# workstation can reach the load balancer directly -- a check against it would fail on the
# network, not on the application. Through CloudFront it is unreachable too: `/health/ready`
# is not under `/v1/*`, so the SPA router rewrites it to the document and a 200 would report
# the console's availability while naming the API.
#
# The 401 above is the stronger signal anyway: it is only produced by application code, so it
# proves the edge behaviour, the origin policy, the load balancer, the target group and a
# running task with a working principal lookup, all in one status. ECS already gates a
# deployment on `/health/ready` from inside the VPC, and `services-stable` in the deploy
# workflow is what waits for it.

# 4. The console bundle was built with a Cognito login, not with the local demo fallback.
#
# `readCompanyAuthConfig` returns null when any of the three Vite variables is absent, and
# the console then sends a demo token the deployed API rejects: a build that looks fine and
# cannot log anybody in. Vite inlines the values, so the login domain is a literal in the
# emitted JavaScript and its presence is checkable from outside.
document="$(curl --silent --show-error --location --max-time 20 "$COMPANY_URL/")"
bundle="$(grep -o '/assets/[A-Za-z0-9._-]*\.js' <<<"$document" | head -1 || true)"
if [[ -z "$bundle" ]]; then
  echo "FAILED   console document names no bundle"
  failures=$((failures + 1))
else
  if curl --silent --show-error --location --max-time 30 "$COMPANY_URL$bundle" |
    grep -q 'amazoncognito\.com'; then
    echo "ok       console bundle carries a Cognito login domain"
  else
    echo "FAILED   console bundle has no Cognito login domain; it would fall back to a demo token"
    failures=$((failures + 1))
  fi
fi

# Not a check, but the header that answers "did my push actually land". A cache that still
# serves the previous build makes every assertion above pass against old code.
echo "info     company edge cache: $(header_of "$COMPANY_URL/" x-cache)"

echo "== $failures failed =="
test "$failures" -eq 0
