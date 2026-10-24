/**
 * Note d'un film, avec sa source : « IMDb 8,5 » (jaune IMDb) ou « TMDB 7,1 ».
 * ----------------------------------------------------------------
 * Le serveur choisit la note la plus fiable (IMDb dès 1 000 votes, sinon
 * TMDB dès 50 votes, sinon rien : voir backend/app/services/ratings.py).
 * La source est toujours écrite : un 7 sur IMDb et un 7 sur TMDB ne se
 * valent pas (TMDB note en moyenne plus haut).
 */
import { cn } from "@/lib/utils";

export type RatingSource = "imdb" | "tmdb" | null | undefined;

const SOURCES: Record<"imdb" | "tmdb", { label: string; className: string; title: string }> = {
    imdb: { label: "IMDb", className: "bg-[#F5C518] text-black", title: "Note IMDb" },
    tmdb: { label: "TMDB", className: "bg-white/20 text-white", title: "Note TMDB (pas assez de votes sur IMDb)" },
};

/** « 8,5 » : une décimale, virgule française. */
export const formatRating = (value: number) => value.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function RatingBadge({
    value,
    source,
    votes,
    className,
}: {
    value: number | null | undefined;
    source: RatingSource;
    votes?: number | null;
    className?: string;
}) {
    if (!value || !source || !(source in SOURCES)) return null;
    const s = SOURCES[source];
    return (
        <span
            title={votes ? `${s.title} · ${votes.toLocaleString("fr-FR")} votes` : s.title}
            className={cn(
                "inline-flex items-center overflow-hidden rounded-[5px] bg-black/70 text-[10.5px] font-semibold leading-none text-white backdrop-blur",
                className,
            )}
        >
            <span className={cn("px-1 py-[3px] text-[9.5px] font-extrabold tracking-tight", s.className)}>{s.label}</span>
            <span className="px-1 py-[3px] tabular-nums">{formatRating(value)}</span>
        </span>
    );
}
