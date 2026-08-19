import { Check, ChevronRight } from "lucide-react";

import { ROLE_TRACK_CATEGORIES } from "./role-taxonomy";
import { getRoleCategoryVisual, getRoleDetailIcon } from "./role-visuals";

const legacyCategoryIds: Record<string, string> = {
  개발: "backend",
  데이터: "data",
  "인프라·보안": "devops",
  "제품·기획": "frontend",
};

function resolveSelection(value: string) {
  const normalized = value.trim();
  const prefixedCategory = ROLE_TRACK_CATEGORIES.find((category) =>
    normalized.startsWith(`${category.label} · `),
  );
  const matchedCategory = ROLE_TRACK_CATEGORIES.find(
    (category) =>
      category.label === normalized ||
      category.id === normalized ||
      category.roles.some(
        (role) =>
          role.label === normalized ||
          role.id === normalized ||
          normalized === `${category.label} · ${role.label}`,
      ),
  );
  const category =
    matchedCategory ??
    prefixedCategory ??
    ROLE_TRACK_CATEGORIES.find(
      (item) => item.id === legacyCategoryIds[normalized],
    ) ??
    ROLE_TRACK_CATEGORIES[0];
  const role =
    category.roles.find(
      (item) =>
        item.label === normalized ||
        item.id === normalized ||
        normalized === `${category.label} · ${item.label}`,
    ) ?? null;
  const customRole =
    !role && normalized.startsWith(`${category.label} · `)
      ? normalized.slice(category.label.length + 3)
      : "";

  return { category, customRole, role };
}

export function RoleCategoryField({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string, suggestedTitle?: string) => void;
}) {
  const {
    category: selectedCategory,
    customRole,
    role: selectedRole,
  } = resolveSelection(value);

  return (
    <div className="overflow-hidden border-y border-border bg-surface">
      <div className="grid min-h-[430px] grid-cols-[190px_minmax(0,1fr)] max-md:grid-cols-1">
        <div className="border-r border-border bg-surface-muted px-3 py-4 max-md:border-r-0 max-md:border-b">
          <div className="mb-3 flex items-center justify-between px-2">
            <strong className="text-[10px] font-semibold text-muted">
              직무 카테고리
            </strong>
            <span className="text-[10px] text-subtle">
              {ROLE_TRACK_CATEGORIES.length}개
            </span>
          </div>
          <div className="grid gap-1 max-md:grid-cols-2">
            {ROLE_TRACK_CATEGORIES.map((category) => {
              const selected = category.id === selectedCategory.id;
              return (
                <button
                  key={category.id}
                  className={`flex min-h-12 w-full items-center gap-2 px-2 text-left text-xs transition-colors ${
                    selected
                      ? "bg-surface font-semibold text-ink"
                      : "text-muted hover:bg-surface hover:text-ink"
                  }`}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => onChange(category.label)}
                >
                  <img
                    alt=""
                    className="size-9 shrink-0 object-contain"
                    src={getRoleCategoryVisual(category.id).icon}
                  />
                  <span className="min-w-0 flex-1 truncate">
                    {category.label}
                  </span>
                  <ChevronRight
                    aria-hidden="true"
                    className={selected ? "text-brand" : "text-subtle"}
                    size={14}
                  />
                </button>
              );
            })}
          </div>
        </div>

        <div className="min-w-0">
          <header className="border-b border-border px-6 py-5">
            <span className="text-[10px] font-semibold text-brand">
              선택한 직무
            </span>
            <h3 className="mt-1 text-lg font-semibold text-ink">
              {selectedCategory.label}
            </h3>
            <p className="mt-1 text-xs leading-5 text-muted">
              {selectedCategory.description}
            </p>
          </header>

          <div className="max-h-[350px] space-y-1 overflow-y-auto p-3">
            <div
              className={`flex items-center gap-3 border-b border-b-border border-l-4 px-3 py-3 ${
                customRole
                  ? "border-l-brand bg-brand-soft"
                  : "border-l-transparent"
              }`}
            >
              <img
                alt=""
                className="size-11 shrink-0 object-contain"
                src={getRoleDetailIcon(null)}
              />
              <label className="min-w-0 flex-1">
                <strong className="block text-xs text-ink">
                  세부 직무 직접 입력
                </strong>
                <input
                  className="mt-1 min-h-9 w-full border-0 border-b border-border bg-transparent px-0 text-sm outline-none focus:border-brand"
                  value={customRole}
                  placeholder={`예: ${
                    selectedCategory.roles[0]?.label ??
                    `${selectedCategory.label} 엔지니어`
                  }`}
                  onChange={(event) => {
                    const next = event.target.value;
                    onChange(
                      next
                        ? `${selectedCategory.label} · ${next}`
                        : selectedCategory.label,
                      next || undefined,
                    );
                  }}
                />
              </label>
              {customRole ? (
                <span className="grid size-5 shrink-0 place-items-center rounded-full bg-brand text-white">
                  <Check aria-hidden="true" size={12} />
                </span>
              ) : null}
            </div>
            <p className="px-3 pt-3 text-[10px] font-semibold text-muted">
              추천 세부 직무
            </p>
            {selectedCategory.roles.map((role) => (
              <RoleRow
                key={role.id}
                description={role.description}
                focusAreas={role.focusAreas.slice(0, 3)}
                icon={getRoleDetailIcon(role.id)}
                label={role.label}
                selected={selectedRole?.id === role.id}
                onClick={() =>
                  onChange(
                    `${selectedCategory.label} · ${role.label}`,
                    role.label,
                  )
                }
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RoleRow({
  description,
  focusAreas,
  icon,
  label,
  selected,
  onClick,
}: {
  description: string;
  focusAreas?: string[];
  icon: string;
  label: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      className={`flex w-full items-center gap-3 border-b border-b-border border-l-4 px-3 py-3 text-left transition-colors ${
        selected
          ? "border-l-brand bg-brand-soft"
          : "border-l-transparent hover:bg-surface-muted"
      }`}
      type="button"
      aria-pressed={selected}
      onClick={onClick}
    >
      <img alt="" className="size-11 shrink-0 object-contain" src={icon} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <strong
            className={`text-sm ${selected ? "text-brand" : "text-ink"}`}
          >
            {label}
          </strong>
          <small className="text-xs text-muted">{description}</small>
        </span>
        {focusAreas?.length ? (
          <span className="mt-2 flex flex-wrap gap-1.5">
            {focusAreas.map((area) => (
              <span
                className="border border-border bg-surface px-2 py-0.5 text-[10px] text-muted"
                key={area}
              >
                {area}
              </span>
            ))}
          </span>
        ) : null}
      </span>
      {selected ? (
        <span className="grid size-5 shrink-0 place-items-center rounded-full bg-brand text-white">
          <Check aria-hidden="true" size={12} />
        </span>
      ) : null}
    </button>
  );
}
