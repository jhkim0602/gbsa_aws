import type { CompanyPosition } from "../company/types";

export function isPositionArchived(
  position: CompanyPosition,
  today = localDateKey(),
) {
  return (
    position.status === "closed" ||
    Boolean(
      position.recruitmentEndAt && position.recruitmentEndAt < today,
    )
  );
}

export function isPositionRecruiting(
  position: CompanyPosition,
  today = localDateKey(),
) {
  if (position.status !== "active") return false;
  if (
    position.recruitmentStartAt &&
    today < position.recruitmentStartAt
  ) {
    return false;
  }
  return (
    !position.recruitmentEndAt || today <= position.recruitmentEndAt
  );
}

function localDateKey() {
  const current = new Date();
  const month = String(current.getMonth() + 1).padStart(2, "0");
  const day = String(current.getDate()).padStart(2, "0");
  return `${current.getFullYear()}-${month}-${day}`;
}
