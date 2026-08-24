// Created: 2026-08-23 23:10
/**
 * Turn a failed review write into something the reviewer can act on.
 *
 * Review writes used to report success unconditionally: the override call was fired without
 * `await` and the confirmation rendered next to it, and the decision buttons had no catch at all.
 * A reviewer who overruled a score, or recorded a hire/no-hire, was told it was recorded whether
 * or not the server accepted it — and re-opening the applicant showed the judgement gone.
 *
 * `companyRequest` already puts the server's `detail` on the thrown error, so the reason is
 * available; it just had nowhere to go. Read it the way the rest of the console does — by shape
 * rather than by class — so this module does not have to depend on the transport.
 */
export function reviewErrorMessage(cause: unknown, fallback: string): string {
  const status = readField(cause, "status");
  if (status === 401 || status === 403) {
    return "권한이 없어 기록하지 못했습니다. 다시 로그인한 뒤 시도해 주세요.";
  }
  if (status === 409) {
    return "다른 곳에서 먼저 기록된 내용입니다. 새로고침 후 다시 시도해 주세요.";
  }
  const detail = readField(cause, "detail");
  if (typeof detail === "string" && detail.trim()) {
    return `${fallback} 서버 응답: ${detail.trim()}`;
  }
  return fallback;
}

function readField(cause: unknown, field: string): unknown {
  return typeof cause === "object" && cause !== null && field in cause
    ? (cause as Record<string, unknown>)[field]
    : null;
}
