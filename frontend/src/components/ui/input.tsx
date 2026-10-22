import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Champ de saisie « rempli » iOS : fond gris, pas de bordure, coins
 * arrondis. 16 px de texte sur mobile : en dessous, Safari iPhone zoome
 * automatiquement sur le champ au toucher (piège classique).
 */
const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-10 w-full rounded-xl border-0 bg-white/[0.08] px-3.5 text-base text-foreground transition-[background-color,box-shadow] duration-200 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground/80 hover:bg-white/[0.1] focus-visible:bg-white/[0.1] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-50 md:text-[15px]",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
