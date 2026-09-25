import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * "▼ 5% vs last week: Rs 94,120" under a figure (Danny's D-55).
 *
 * The previous figure is always shown next to the percentage, so the owner can
 * see what it is measured against, not just a bare arrow. When the previous
 * period is zero there is no percentage to give ("up ∞%" helps nobody), so it
 * says so in words.
 */
interface PeriodDeltaProps {
  current: number;
  previous: number;
  /** "last week", "yesterday", "the previous 3 days" */
  against: string;
  /** Renders the previous figure: formatPKR for money, a count otherwise. */
  format: (value: number) => string;
  /** " to 14:00" when the previous period was cut to match "so far". */
  until?: string;
  compact?: boolean;
  className?: string;
}

export function PeriodDelta({
  current,
  previous,
  against,
  format,
  until = "",
  compact = false,
  className,
}: PeriodDeltaProps) {
  if (current === 0 && previous === 0) {
    return compact ? null : (
      <p className={cn("text-xs text-secondary-400", className)}>
        Nothing {against} either
      </p>
    );
  }

  if (previous === 0) {
    return (
      <p className={cn("text-xs font-medium text-success-700", className)}>
        {compact ? "new" : `None ${against}${until}`}
      </p>
    );
  }

  const pct = Math.round(((current - previous) / previous) * 100);
  const Icon = pct > 0 ? ArrowUpRight : pct < 0 ? ArrowDownRight : Minus;
  const tone =
    pct > 0 ? "text-success-700" : pct < 0 ? "text-danger-600" : "text-secondary-500";

  if (compact) {
    return (
      <span
        className={cn("inline-flex items-center gap-0.5 text-xs font-medium", tone, className)}
        title={`${format(previous)} ${against}${until}`}
      >
        <Icon className="h-3 w-3" aria-hidden="true" />
        {pct === 0 ? "same" : `${Math.abs(pct)}%`}
      </span>
    );
  }

  return (
    <p className={cn("flex flex-wrap items-center gap-1 text-xs", className)}>
      <span className={cn("inline-flex items-center gap-0.5 font-semibold", tone)}>
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {pct === 0 ? "No change" : `${pct > 0 ? "Up" : "Down"} ${Math.abs(pct)}%`}
      </span>
      <span className="text-secondary-500">
        vs {against}: {format(previous)}
        {until}
      </span>
    </p>
  );
}
