import {
  ArrowRight,
  Database,
  FileChartColumn,
  MessageSquareText,
  Sparkles,
} from "lucide-react";

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
    <aside className="hiring-ai-flow" aria-label={title}>
      <div className="hiring-ai-flow__intro">
        <Sparkles aria-hidden="true" size={15} />
        <div>
          <strong>{title}</strong>
          <p>{description}</p>
        </div>
      </div>
      <ol>
        {stages.map((stage, index) => {
          const Icon = icons[index];
          return (
            <li key={stage}>
              <span>
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
