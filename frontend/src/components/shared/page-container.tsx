/**
 * Conteneur standard du contenu d'une page : marges alignées sur le header,
 * largeur max homogène, espacement vertical entre sections.
 * (Avant : chaque page avait sa largeur — 3xl, 4xl, 1400px, 1500px, rien…)
 */
import { cn } from "@/lib/utils";

export function PageContainer({
    children,
    className,
    size = "wide",
}: {
    children: React.ReactNode;
    className?: string;
    /** wide = grilles de médias / dashboards ; narrow = formulaires, réglages. */
    size?: "wide" | "narrow";
}) {
    return (
        <div className="px-3 pb-6 pt-5 md:px-5 lg:pl-0 lg:pr-5">
            <div className={cn("mx-auto w-full space-y-6", size === "wide" ? "max-w-[1680px]" : "max-w-5xl", className)}>
                {children}
            </div>
        </div>
    );
}
