import { cn } from "@/lib/utils"

/** Bloc de chargement : gris qui pulse doucement (comme les listes iOS). */
function Skeleton({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("shimmer rounded-lg", className)}
      {...props}
    />
  )
}

export { Skeleton }
