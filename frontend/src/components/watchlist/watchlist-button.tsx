"use client";

/**
 * Bouton « + Ma liste » / « ✓ Dans ma liste » (fiche, recommandation…).
 * ----------------------------------------------------------------
 * Ajoute le titre à la liste du profil choisi (voir useWatchlistProfile).
 * `request` : si le titre n'est pas dans la médiathèque, le serveur le
 * demande aussi à Radarr / Sonarr (le toast le confirme).
 */
import { Check, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { Button, type ButtonProps } from "@/components/ui/button";
import { useFamilyProfiles } from "@/hooks/use-family-profiles";
import {
    useAddToWatchlist,
    useRemoveFromWatchlist,
    useWatchlist,
    useWatchlistProfile,
    watchlistKey,
    type WatchlistTarget,
} from "@/hooks/use-watchlist";
import { cn } from "@/lib/utils";

export function WatchlistButton({
    target,
    request = false,
    size = "lg",
    variant = "secondary",
    iconOnly = false,
    className,
}: {
    target: WatchlistTarget;
    request?: boolean;
    size?: ButtonProps["size"];
    variant?: ButtonProps["variant"];
    iconOnly?: boolean;
    className?: string;
}) {
    const [profile] = useWatchlistProfile();
    const { data: profiles } = useFamilyProfiles();
    const { data: list } = useWatchlist(profile);
    const add = useAddToWatchlist(profile);
    const remove = useRemoveFromWatchlist(profile);
    // Série des suggestions TMDB : pas encore d'id TVDB (le serveur le résout
    // à l'ajout) ; on ne sait alors pas dire si elle est déjà dans la liste.
    const key = watchlistKey(target);
    if (!key && !target.tmdb_id) return null;

    const inList = !!list?.some((i) => i.key === key);
    const busy = add.isPending || remove.isPending;
    // « Ma liste » si un seul profil ; sinon on précise de qui
    const owner = profile ? profiles?.find((p) => p.id === profile)?.name : null;
    const listName = owner ? `liste de ${owner}` : "ma liste";

    const toggle = () => {
        if (inList) {
            remove.mutate(target, {
                onSuccess: () => toast.success(`Retiré de ${listName}`),
                onError: (e) => toast.error("Retrait impossible", { description: e.message }),
            });
            return;
        }
        add.mutate(
            { ...target, request },
            {
                onSuccess: (r) => {
                    const asked = r.download?.status === "ok";
                    toast.success(`Ajouté à ${listName}`, {
                        description: asked
                            ? "Il n'était pas sur le NAS : téléchargement demandé."
                            : r.download?.status === "error"
                              ? `Téléchargement non lancé : ${r.download.message ?? "erreur"}`
                              : undefined,
                    });
                },
                onError: (e) => toast.error("Ajout impossible", { description: e.message }),
            },
        );
    };

    const label = inList ? "Dans ma liste" : "Ma liste";
    return (
        <Button
            size={iconOnly ? (size === "sm" ? "icon-sm" : "icon") : size}
            variant={inList ? "tinted" : variant}
            onClick={toggle}
            disabled={busy}
            aria-pressed={inList}
            aria-label={inList ? `Retirer de ${listName}` : `Ajouter à ${listName}`}
            title={inList ? `Retirer de ${listName}` : `Ajouter à ${listName}`}
            className={cn(!iconOnly && "flex-1 sm:flex-none", className)}
        >
            {busy ? <Loader2 className="animate-spin" /> : inList ? <Check /> : <Plus />}
            {!iconOnly && label}
        </Button>
    );
}
