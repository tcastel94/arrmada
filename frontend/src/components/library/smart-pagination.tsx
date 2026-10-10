"use client";

/**
 * Pagination « intelligente » : 1 … 4 5 6 … 20.
 * ----------------------------------------------------------------
 * Avant : seules les 7 premières pages étaient cliquables (impossible
 * d'atteindre la page 12 sans cliquer 11 fois sur « Suivant »).
 * Ici : première et dernière page toujours visibles, une fenêtre autour de
 * la page courante, et des « … » pour le reste. Sur mobile, on remplace les
 * numéros par un compteur « 5 / 20 » pour garder de gros boutons au pouce.
 */
import { motion } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

type PageToken = number | "gap-start" | "gap-end";

/** Liste des pages à afficher (avec trous) autour de `page`. */
export function pageWindow(page: number, total: number, siblings = 1): PageToken[] {
    if (total <= 1) return [1];
    // Assez peu de pages : on les montre toutes.
    if (total <= 5 + siblings * 2) return Array.from({ length: total }, (_, i) => i + 1);

    const start = Math.max(2, page - siblings);
    const end = Math.min(total - 1, page + siblings);
    const tokens: PageToken[] = [1];
    // Un « … » qui ne cacherait qu'une seule page est remplacé par cette page.
    if (start > 3) tokens.push("gap-start");
    else if (start === 3) tokens.push(2);
    for (let p = start; p <= end; p++) tokens.push(p);
    if (end < total - 2) tokens.push("gap-end");
    else if (end === total - 2) tokens.push(total - 1);
    tokens.push(total);
    return tokens;
}

export function SmartPagination({
    page,
    totalPages,
    onChange,
    layoutId,
    className,
}: {
    page: number;
    totalPages: number;
    onChange: (page: number) => void;
    /** Identifiant unique de la pastille animée de la page active. */
    layoutId: string;
    className?: string;
}) {
    if (totalPages <= 1) return null;
    const tokens = pageWindow(page, totalPages);

    return (
        <nav aria-label="Pagination" className={cn("flex items-center justify-center gap-2", className)}>
            <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => onChange(page - 1)}
                aria-label="Page précédente"
                className="h-9 gap-1 px-3"
            >
                <ChevronLeft />
                <span className="hidden sm:inline">Précédente</span>
            </Button>

            {/* Mobile : compteur compact */}
            <span className="min-w-[4.5rem] text-center text-sm tabular-nums text-muted-foreground sm:hidden">
                <span className="font-semibold text-foreground">{page}</span> / {totalPages}
            </span>

            {/* Desktop : numéros de page avec pastille animée */}
            <div className="glass hidden items-center gap-0.5 rounded-xl p-1 sm:flex">
                {tokens.map((token) =>
                    typeof token === "number" ? (
                        <button
                            key={token}
                            type="button"
                            onClick={() => onChange(token)}
                            aria-label={`Page ${token}`}
                            aria-current={token === page ? "page" : undefined}
                            className={cn(
                                "relative h-8 min-w-8 rounded-lg px-2 text-sm font-medium tabular-nums transition-colors",
                                token === page ? "text-primary-foreground" : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground",
                            )}
                        >
                            {token === page && (
                                <motion.span
                                    layoutId={layoutId}
                                    transition={SPRING}
                                    aria-hidden
                                    className="absolute inset-0 rounded-lg bg-gradient-to-r from-primary to-[hsl(200_100%_62%)] shadow-[0_6px_20px_-6px_hsl(var(--primary)/0.8)]"
                                />
                            )}
                            <span className="relative z-[1]">{token}</span>
                        </button>
                    ) : (
                        <span key={token} aria-hidden className="px-1.5 text-sm text-muted-foreground/60">
                            …
                        </span>
                    ),
                )}
            </div>

            <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => onChange(page + 1)}
                aria-label="Page suivante"
                className="h-9 gap-1 px-3"
            >
                <span className="hidden sm:inline">Suivante</span>
                <ChevronRight />
            </Button>
        </nav>
    );
}
