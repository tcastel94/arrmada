import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        success: "border-emerald-500/30 bg-emerald-500/15 text-emerald-400",
        warning: "border-amber-500/30 bg-amber-500/15 text-amber-400",
        default:
          "border-primary/30 bg-primary/15 text-primary",
        secondary:
          "border-white/[0.06] bg-secondary text-secondary-foreground",
        destructive:
          "border-red-500/30 bg-red-500/15 text-red-400",
        outline: "border-white/[0.1] text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
