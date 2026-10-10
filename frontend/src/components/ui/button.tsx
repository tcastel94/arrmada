import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Bouton — variantes alignées sur le design system « Neon Armada ».
 * - default : dégradé bleu→cyan lumineux (action principale)
 * - outline / secondary / ghost : verre discret
 * - destructive : rouge avec halo
 * Micro-interaction commune : léger enfoncement au clic (active:scale).
 */
const buttonVariants = cva(
  "relative inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-all duration-200 ease-smooth active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/70 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-primary to-[hsl(200_100%_62%)] text-primary-foreground font-semibold shadow-[0_0_0_1px_hsl(var(--primary)/0.5),0_8px_24px_-8px_hsl(var(--primary)/0.7)] hover:shadow-[0_0_0_1px_hsl(var(--primary)/0.7),0_10px_32px_-6px_hsl(var(--primary)/0.9)] hover:brightness-110",
        destructive:
          "bg-gradient-to-r from-red-500 to-rose-500 text-white font-semibold shadow-[0_0_0_1px_rgb(239_68_68/0.5),0_8px_24px_-8px_rgb(239_68_68/0.7)] hover:brightness-110",
        outline:
          "border border-white/[0.09] bg-white/[0.03] backdrop-blur hover:bg-white/[0.07] hover:border-white/[0.16] hover:text-foreground",
        secondary:
          "bg-secondary/80 text-secondary-foreground border border-white/[0.05] hover:bg-secondary",
        ghost: "hover:bg-white/[0.06] hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline active:scale-100",
        glow:
          "border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20 hover:shadow-[0_0_24px_-4px_hsl(var(--primary)/0.7)]",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-6 text-base",
        icon: "h-9 w-9",
        "icon-sm": "h-8 w-8 rounded-lg",
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
