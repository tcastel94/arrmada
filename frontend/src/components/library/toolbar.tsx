"use client";

/**
 * Briques des barres d'outils de la Bibliothèque.
 * ----------------------------------------------------------------
 *  - StickyToolbar : barre en verre collée sous le header au défilement
 *  - SearchField   : champ de recherche avec icône, spinner et bouton ✕
 *  - RemovableChip : filtre actif supprimable d'un clic
 */
import { forwardRef, type ReactNode } from "react";
import { motion } from "framer-motion";
import { Loader2, Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";

/**
 * Barre collante sous le header (68 px + marge). Sur mobile elle reste dans
 * le flux (non collante) pour ne pas manger la moitié de l'écran.
 */
export function StickyToolbar({ children, className }: { children: ReactNode; className?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.1 }}
            className={cn(
                "glass z-20 rounded-2xl p-2 shadow-[0_18px_40px_-24px_rgba(0,0,0,0.9)] sm:sticky sm:top-[84px]",
                className,
            )}
        >
            {children}
        </motion.div>
    );
}

interface SearchFieldProps {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    /** Affiche un spinner à droite (requête en cours). */
    loading?: boolean;
    onSubmit?: () => void;
    size?: "md" | "lg";
    autoFocus?: boolean;
    ariaLabel: string;
    className?: string;
    id?: string;
}

export const SearchField = forwardRef<HTMLInputElement, SearchFieldProps>(function SearchField(
    { value, onChange, placeholder, loading, onSubmit, size = "md", autoFocus, ariaLabel, className, id },
    ref,
) {
    const lg = size === "lg";
    return (
        <div className={cn("relative min-w-0", className)}>
            <Search
                aria-hidden
                className={cn(
                    "pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground/60",
                    lg ? "left-4 h-5 w-5" : "left-3 h-4 w-4",
                )}
            />
            <Input
                ref={ref}
                id={id}
                type="search"
                value={value}
                autoFocus={autoFocus}
                aria-label={ariaLabel}
                placeholder={placeholder}
                onChange={(e) => onChange(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === "Enter") onSubmit?.();
                    if (e.key === "Escape" && value) {
                        e.preventDefault();
                        onChange("");
                    }
                }}
                className={cn(
                    // Masque la croix native du type=search (on a la nôtre).
                    "[&::-webkit-search-cancel-button]:appearance-none",
                    lg ? "h-14 rounded-2xl pl-12 pr-12 text-base md:text-lg" : "h-9 pl-9 pr-9",
                )}
            />
            <div className={cn("absolute top-1/2 flex -translate-y-1/2 items-center", lg ? "right-3" : "right-2")}>
                {loading ? (
                    <Loader2 className={cn("animate-spin text-primary", lg ? "h-5 w-5" : "h-4 w-4")} aria-label="Recherche en cours" />
                ) : value ? (
                    <motion.button
                        type="button"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={SPRING}
                        onClick={() => onChange("")}
                        aria-label="Effacer la recherche"
                        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                    >
                        <X className={lg ? "h-4 w-4" : "h-3.5 w-3.5"} />
                    </motion.button>
                ) : null}
            </div>
        </div>
    );
});

/** Chip de filtre actif : cliquer dessus retire le filtre. */
export function RemovableChip({ label, onRemove }: { label: ReactNode; onRemove: () => void }) {
    return (
        <motion.button
            layout
            type="button"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={SPRING}
            onClick={onRemove}
            data-active="true"
            className="chip group"
            aria-label={`Retirer le filtre ${typeof label === "string" ? label : ""}`.trim()}
        >
            {label}
            <X className="h-3 w-3 opacity-60 transition-opacity group-hover:opacity-100" />
        </motion.button>
    );
}
