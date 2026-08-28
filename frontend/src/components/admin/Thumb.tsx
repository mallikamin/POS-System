import { Image as ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const SIZES = {
  sm: "h-6 w-6 rounded",
  md: "h-9 w-9 rounded-md",
  lg: "h-14 w-14 rounded-lg",
} as const;

interface ThumbProps {
  src: string | null | undefined;
  alt: string;
  size?: keyof typeof SIZES;
  className?: string;
}

/**
 * The small square photograph beside a name in a table or card.
 *
 * One component so the ingredient photo looks the same on the ingredient
 * list, the recipe lines, the stock table, a purchase order and a supplier's
 * catalogue. With no photo it shows a quiet placeholder rather than
 * collapsing, so columns stay aligned whether or not a row has one.
 */
export function Thumb({ src, alt, size = "md", className }: ThumbProps) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden border border-secondary-200 bg-secondary-100 text-secondary-400",
        SIZES[size],
        className
      )}
    >
      {src ? (
        <img
          src={src}
          alt={alt}
          loading="lazy"
          className="h-full w-full object-cover"
        />
      ) : (
        <ImageIcon className="h-1/2 w-1/2" aria-hidden="true" />
      )}
    </span>
  );
}
