"use client";

/**
 * Rangée « Reprendre » de l'Accueil.
 * ----------------------------------------------------------------
 * Les films et épisodes commencés sur les TV, en vignettes paysage
 * (voir ContinueCard). Masquée s'il n'y a rien en cours (pas de section
 * vide sur l'Accueil).
 */
import { Section } from "@/components/shared/section";
import { Shelf } from "@/components/shared/shelf";
import { ContinueCard, continueKey } from "@/components/media/continue-card";
import { useWatchSummary } from "@/hooks/use-watch";

export function ContinueShelf() {
    const { data } = useWatchSummary();
    const rows = (data?.continue ?? []).slice(0, 12);
    if (rows.length === 0) return null;

    return (
        <Section title="Reprendre" href="/media/continue">
            <Shelf>
                {rows.map((row) => (
                    <ContinueCard key={continueKey(row)} row={row} className="w-[260px] shrink-0 sm:w-[300px]" />
                ))}
            </Shelf>
        </Section>
    );
}
