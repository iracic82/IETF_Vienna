import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase",
  {
    variants: {
      variant: {
        default: "bg-[var(--color-bg-elevated)] text-[var(--color-text-muted)] border border-[var(--color-border-subtle)]",
        ok:      "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
        warn:    "bg-amber-500/15  text-amber-300  border border-amber-500/30",
        error:   "bg-red-500/15    text-red-300    border border-red-500/30",
        accent:  "bg-[var(--color-accent)]/15 text-[var(--color-accent-soft)] border border-[var(--color-accent)]/30",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
