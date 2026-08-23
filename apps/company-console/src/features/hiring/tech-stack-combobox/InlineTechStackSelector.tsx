import { Check, Plus, Search, X } from "lucide-react";
import { useMemo, useState, type KeyboardEvent } from "react";

import {
  TECH_CATEGORY_LIST,
  getTechCategory,
  matchCategoryByQuery,
} from "./tech-categories";
import { getAllTechLabels, getTechLogo } from "./tech-logos";

function normalize(value: string) {
  return value.trim().toLowerCase();
}

export function InlineTechStackSelector({
  value,
  onChange,
}: {
  value: string[];
  onChange: (next: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const allLabels = useMemo(
    () => getAllTechLabels().map((item) => item.label),
    [],
  );
  const selected = useMemo(
    () => new Set(value.map((label) => normalize(label))),
    [value],
  );
  const trimmedQuery = query.trim();
  const lowerQuery = normalize(query);
  const categoryMatch = useMemo(
    () => matchCategoryByQuery(trimmedQuery),
    [trimmedQuery],
  );
  const filtered = useMemo(() => {
    if (!lowerQuery) return [];
    return allLabels
      .filter(
        (label) =>
          getTechCategory(label) === categoryMatch ||
          normalize(label).includes(lowerQuery),
      )
      .slice(0, 120);
  }, [allLabels, categoryMatch, lowerQuery]);
  const grouped = useMemo(
    () =>
      TECH_CATEGORY_LIST.map((category) => ({
        category,
        labels: filtered.filter(
          (label) => getTechCategory(label) === category.key,
        ),
      })).filter((group) => group.labels.length > 0),
    [filtered],
  );
  const canAddCustom = Boolean(
    trimmedQuery &&
    !selected.has(lowerQuery) &&
    !allLabels.some((label) => normalize(label) === lowerQuery),
  );

  function add(label: string) {
    const trimmed = label.trim();
    if (!trimmed || selected.has(normalize(trimmed))) return;
    onChange([...value, trimmed]);
    setQuery("");
  }

  function remove(label: string) {
    const target = normalize(label);
    onChange(value.filter((item) => normalize(item) !== target));
  }

  function toggle(label: string) {
    if (selected.has(normalize(label))) remove(label);
    else add(label);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter" || !trimmedQuery) return;
    event.preventDefault();
    const exact = allLabels.find((label) => normalize(label) === lowerQuery);
    add(exact ?? trimmedQuery);
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface">
      <div className="border-b border-border-muted px-5 py-4">
        <div className="relative">
          <Search
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted"
          />
          <input
            autoFocus
            aria-label="기술 스택 검색"
            className="h-11 w-full rounded-lg border border-border bg-surface pr-3 pl-10 text-sm outline-none placeholder:text-muted focus:border-brand focus:ring-1 focus:ring-brand"
            value={query}
            placeholder='기술명 또는 "백엔드", "데이터" 같은 카테고리를 검색하세요'
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5" aria-label="기술 카테고리">
          {TECH_CATEGORY_LIST.filter((category) => category.key !== "etc").map(
            (category) => {
              const active = categoryMatch === category.key;
              return (
                <button
                  key={category.key}
                  className={`inline-flex min-h-8 items-center rounded-full border px-3 text-[11px] font-semibold transition-colors ${
                    active
                      ? "border-brand bg-brand-soft text-brand"
                      : "border-border bg-surface text-muted hover:border-brand hover:text-brand"
                  }`}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setQuery(category.label)}
                >
                  {category.label}
                </button>
              );
            },
          )}
        </div>
      </div>

      <div className="grid min-h-[360px] grid-cols-[230px_minmax(0,1fr)] max-md:grid-cols-1">
        <aside className="border-r border-border-muted bg-surface-muted p-4 max-md:border-r-0 max-md:border-b">
          <div className="flex items-center justify-between">
            <strong className="text-xs text-ink">선택한 기술</strong>
            <span className="text-[10px] text-muted">{value.length}개</span>
          </div>
          {value.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {value.map((label) => {
                const logo = getTechLogo(label);
                return (
                  <span
                    key={label}
                    className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-border bg-surface px-2 text-xs font-semibold text-ink"
                  >
                    <TechLogo label={label} src={logo?.src} />
                    {label}
                    <button
                      aria-label={`${label} 제거`}
                      className="grid size-5 place-items-center rounded-full text-muted hover:bg-danger-soft hover:text-danger"
                      type="button"
                      onClick={() => remove(label)}
                    >
                      <X aria-hidden="true" size={12} />
                    </button>
                  </span>
                );
              })}
            </div>
          ) : (
            <p className="mt-3 text-xs leading-5 text-muted">
              오른쪽에서 기술을 검색하고 선택해 주세요.
            </p>
          )}
        </aside>

        <div
          className="max-h-[440px] min-h-[360px] overflow-y-auto p-4"
          role="listbox"
          aria-label="기술 검색 결과"
          aria-multiselectable="true"
        >
          {!lowerQuery ? (
            <div className="grid min-h-[300px] place-items-center text-center text-sm text-muted">
              카테고리를 선택하거나 기술명을 검색해 주세요.
            </div>
          ) : grouped.length === 0 && !canAddCustom ? (
            <div className="grid min-h-[300px] place-items-center text-center text-sm text-muted">
              일치하는 기술이 없습니다.
            </div>
          ) : (
            <div className="grid gap-5">
              {grouped.map(({ category, labels }) => (
                <section key={category.key}>
                  <div className="mb-2 flex items-baseline gap-2">
                    <strong className="text-xs text-ink">
                      {category.label}
                    </strong>
                    <span className="text-[10px] text-muted">
                      {labels.length}개
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 max-sm:grid-cols-1">
                    {labels.map((label) => {
                      const logo = getTechLogo(label);
                      const isSelected = selected.has(normalize(label));
                      return (
                        <button
                          key={label}
                          aria-selected={isSelected}
                          className={`flex min-h-11 items-center gap-2 rounded-lg border px-3 text-left text-sm transition-colors ${
                            isSelected
                              ? "border-brand bg-brand-soft text-brand"
                              : "border-border bg-surface text-ink hover:border-brand"
                          }`}
                          role="option"
                          type="button"
                          onClick={() => toggle(label)}
                        >
                          <TechLogo label={label} src={logo?.src} />
                          <span className="min-w-0 flex-1 truncate">
                            {label}
                          </span>
                          {isSelected ? (
                            <Check
                              aria-hidden="true"
                              className="shrink-0"
                              size={15}
                            />
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
              {canAddCustom ? (
                <button
                  className="flex min-h-11 items-center gap-2 rounded-lg border border-dashed border-brand bg-brand-soft px-3 text-left text-sm text-brand"
                  role="option"
                  aria-selected="false"
                  type="button"
                  onClick={() => add(trimmedQuery)}
                >
                  <Plus aria-hidden="true" size={15} />
                  직접 추가: <strong>{trimmedQuery}</strong>
                </button>
              ) : null}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TechLogo({ label, src }: { label: string; src?: string }) {
  return (
    <span
      aria-hidden="true"
      className="grid size-6 shrink-0 place-items-center rounded-md bg-surface-muted bg-contain bg-center bg-no-repeat text-[9px] font-bold text-muted"
      style={src ? { backgroundImage: `url(${src})` } : undefined}
    >
      {src ? null : label.slice(0, 1).toUpperCase()}
    </span>
  );
}
