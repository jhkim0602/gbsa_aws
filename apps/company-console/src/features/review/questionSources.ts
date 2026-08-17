/** How a submission excerpt is labelled wherever it is shown to a reviewer. */
export function sourceTypeLabel(sourceType: string) {
  return sourceType === "candidate_code_unit" ? "Git 코드" : "첨부 자료";
}

export function formatLocator(locator: Record<string, unknown>) {
  const page = locator.page_number ?? locator.page;
  const path = locator.path;
  const symbol = locator.symbol;
  if (typeof path === "string") {
    return [path, typeof symbol === "string" ? symbol : null]
      .filter(Boolean)
      .join(" · ");
  }
  if (typeof page === "number" || typeof page === "string") {
    return `${page}페이지`;
  }
  return "원문 위치";
}
