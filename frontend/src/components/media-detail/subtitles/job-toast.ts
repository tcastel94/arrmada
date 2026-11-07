import { toast } from "sonner";
import type { SubtitleJob } from "@/hooks/use-subtitles";

/**
 * Toasts d'une recherche de sous-titres suivie jusqu'au bout
 * (voir followSubtitleJob) : un seul toast, mis à jour à chaque étape,
 * puis remplacé par le résultat.
 */
export function startSubtitleToast(what: string) {
    const id = toast.loading(`Recherche de sous-titres FR — ${what}`, {
        description: "Bazarr interroge ses fournisseurs (parfois plus d'une minute pour un anime).",
    });
    return {
        /** Étape en cours (« Recherche élargie », « Recalage sur le son »…) */
        progress: (job: SubtitleJob) =>
            toast.loading(`Recherche de sous-titres FR — ${what}`, { id, description: job.phase }),
        /** Résultat final : trouvé, rien, panne ou toujours en cours */
        done: (job: SubtitleJob) => {
            const added = job.added?.length ? `Disponible sur la TV : ${job.added.join(", ")}` : undefined;
            if (job.status === "found") toast.success(job.message, { id, description: added });
            else if (job.status === "none") toast.warning(job.message, { id });
            else if (job.status === "pending")
                toast.info("La recherche continue en arrière-plan", {
                    id,
                    description: "Le sous-titre apparaîtra tout seul ici et sur la TV.",
                });
            else toast.error("Recherche impossible", { id, description: job.message });
        },
        failed: (e: Error) => toast.error("Recherche impossible", { id, description: e.message }),
    };
}
