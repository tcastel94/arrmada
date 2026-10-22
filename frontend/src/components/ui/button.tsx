import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Bouton — design system « Épuré » (façon iOS).
 * - default     : aplat bleu #4A9EFF, texte blanc (action principale, une par écran)
 * - secondary   : gris « rempli » iOS (actions courantes)
 * - outline     : même gris avec filet (compat ancien thème)
 * - ghost       : transparent, gris au survol (barres d'outils)
 * - tinted      : bleu translucide, texte bleu (action mise en avant sans crier)
 * - destructive : rouge système
 * - link        : texte bleu seul
 * Retour d'appui commun : léger enfoncement + atténuation, comme sur iPhone.
 */
const buttonVariants = cva(
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-xl text-[15px] font-semibold transition-[transform,background-color,opacity,color] duration-200 ease-smooth active:scale-[0.97] active:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-40 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-white/[0.08] bg-secondary text-foreground hover:bg-accent",
        secondary: "bg-secondary text-foreground hover:bg-accent",
        tinted: "bg-primary/15 text-primary hover:bg-primary/20",
        ghost: "font-medium text-foreground/90 hover:bg-white/[0.08] hover:text-foreground",
        link: "font-medium text-primary hover:opacity-80 active:scale-100",
        // Ancien nom (« lumineux ») : devient la variante teintée.
        glow: "bg-primary/15 text-primary hover:bg-primary/20",
      },
      size: {
        default: "h-10 px-4",
        sm: "h-8 rounded-lg px-3 text-[13px]",
        lg: "h-12 rounded-2xl px-6 text-[17px]",
        icon: "h-10 w-10 rounded-full",
        "icon-sm": "h-8 w-8 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
