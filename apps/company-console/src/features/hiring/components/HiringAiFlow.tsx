import {
  ArrowRight,
  Database,
  FileChartColumn,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

// `#1f8a70` / `#f3f8f6` / `#176b58` have no token — this strip is the one green surface in the
// console, so they stay literal, as the bundle already has them.
const FLOW =
  "grid grid-cols-[minmax(240px,1.1fr)_minmax(320px,1fr)] items-center gap-6" +
  " border-l-[3px] border-l-[#1f8a70] bg-[#f3f8f6] px-[18px] py-4" +
  " mw-780:grid-cols-[minmax(0,1fr)]";

// The `ol` is flex until 620px, where it becomes a 3-up grid; `justify-content` still applies
// to the grid, so both the base `flex-end` and the 780px `flex-start` are kept.
const STAGES =
  "flex list-none items-center justify-end gap-2" +
  " mw-780:justify-start mw-620:grid mw-620:grid-cols-3";

export function HiringAiFlow({
  title,
  description,
  stages,
}: {
  title: string;
  description: string;
  stages: readonly [string, string, string];
}) {
  const icons = [Database, MessageSquareText, FileChartColumn] as const;

  return (
    <aside className={FLOW} aria-label={title}>
      <div className="grid grid-cols-[24px_minmax(0,1fr)] items-start gap-[9px] text-[#176b58]">
        <Sparkles className="mt-px" aria-hidden="true" size={15} />
        <div className="grid gap-[3px]">
          <strong className="text-[11px] text-ink">{title}</strong>
          <p className="text-[9px] leading-[1.55] text-muted">{description}</p>
        </div>
      </div>
      <ol className={STAGES}>
        {stages.map((stage, index) => {
          const Icon = icons[index];
          return (
            <li
              key={stage}
              // `li > svg` is the connecting arrow only — the stage icon is nested inside the
              // span, so hiding direct children at 620px leaves it untouched.
              className="flex items-center gap-2 text-subtle mw-620:[&>svg]:hidden"
            >
              <span className="grid min-w-[90px] justify-items-center gap-[5px] text-center text-[9px] text-ink-secondary mw-620:min-w-0 [&_svg]:text-[#1f8a70]">
                <Icon aria-hidden="true" size={14} />
                {stage}
              </span>
              {index < stages.length - 1 ? (
                <ArrowRight aria-hidden="true" size={13} />
              ) : null}
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
