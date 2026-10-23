/**
 * Conteneur standard du contenu d'une page : marges latérales identiques
 * partout (16 px sur mobile comme iOS, plus large sur ordinateur),
 * largeur maximale homogène, espacement vertical entre sections.
 */
import { cn } from "@/lib/utils";

export function PageContainer({
    children,
    className,
    size = "wide",
}: {
    children: React.ReactNode;
    className?: string;
    /** wide = grilles de médias / tableaux de bord ; narrow = formulaires, réglages. */
    size?: "wide" | "narrow";
}) {
    return (
        <div className="px-4 pb-8 pt-1 md:px-6 lg:px-8">
            <div className={cn("mx-auto w-full space-y-7", size === "wide" ? "max-w-[1600px]" : "max-w-4xl", className)}>
                {children}
            </div>
        </div>
    );
}
