export function statusLabel(status: string) {
  return (
    {
      draft: "초안",
      active: "운영 중",
      open: "운영 중",
      published: "게시됨",
      closed: "종료",
    }[status] ?? status
  );
}

export function statusTone(status: string) {
  return ["active", "open", "published"].includes(status)
    ? "is-success"
    : status === "draft"
      ? "is-warning"
      : "is-neutral";
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

export function formatActivityTime(value: string) {
  return new Intl.DateTimeFormat("ko-KR", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
