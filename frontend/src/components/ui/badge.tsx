import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Pastille de statut : fond teinté discret, texte de la couleur système,
 * sans bordure (style étiquettes iOS / macOS).
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-semibold leading-4 transition-colors",
  {
    variants: {
      variant: {
        success: "bg-success/15 text-success",
        warning: "bg-warning/15 text-warning",
        default: "bg-primary/15 text-primary",
        secondary: "bg-white/[0.09] text-foreground/80",
        destructive: "bg-destructive/15 text-destructive",
        outline: "text-foreground/80 ring-1 ring-inset ring-white/15",
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
