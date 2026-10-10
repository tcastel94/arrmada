"use client";

/**
 * Aperçu d'un titre à ajouter — désormais un simple raccourci vers la fiche
 * détaillée TMDB (RecommendationDetailModal).
 * ----------------------------------------------------------------
 * L'ancien aperçu (affiche + résumé + bouton d'ajout) a été fusionné avec la
 * modale riche portée du serveur : une seule fenêtre, qui montre tout de
 * suite ce que la tuile connaît, puis l'enrichit (casting, bande-annonce,
 * genres…) quand le titre a un ID TMDB. Ce composant garde l'ancienne
 * signature pour ne casser aucun appelant.
 */
import { RecommendationDetailModal } from "@/components/media/recommendation-detail-modal";
import type { AddableItem } from "./adder";

export function AddPreviewDialog({
    item,
    onOpenChange,
    onShowTracking,
}: {
    item: AddableItem | null;
    onOpenChange: (open: boolean) => void;
    onShowTracking?: () => void;
}) {
    return (
        <RecommendationDetailModal
            tmdbId={item?.tmdb_id ?? null}
            mediaType={item?.type}
            preview={item}
            isOpen={!!item}
            onClose={() => onOpenChange(false)}
            onShowTracking={onShowTracking}
        />
    );
}
