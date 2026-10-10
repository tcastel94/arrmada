"use client";

/**
 * Suppression d'un média (ConfirmDialog destructif + options).
 * ----------------------------------------------------------------
 * Corrigé : avant, l'erreur réelle du backend était avalée (« Erreur lors
 * de la suppression ») et la médiathèque n'était pas invalidée (le média
 * supprimé restait affiché). Désormais : message réel, invalidation du
 * cache (dans useDeleteMedia) puis retour à /media.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { useDeleteMedia, type MediaDetail } from "@/hooks/use-media";

export function DeleteMediaDialog({
    media,
    open,
    onOpenChange,
}: {
    media: MediaDetail;
    open: boolean;
    onOpenChange: (v: boolean) => void;
}) {
    const router = useRouter();
    const del = useDeleteMedia();
    const [deleteFiles, setDeleteFiles] = useState(true);
    const [deleteDownloads, setDeleteDownloads] = useState(true);
    const arr = media.type === "movie" ? "Radarr" : "Sonarr";

    return (
        <ConfirmDialog
            open={open}
            onOpenChange={onOpenChange}
            destructive
            title={`Supprimer « ${media.title} » ?`}
            description={`Le ${media.type === "movie" ? "film" : "titre"} sera retiré de ${arr}. Cette action est irréversible.`}
            confirmLabel="Supprimer définitivement"
            onConfirm={async () => {
                try {
                    await del.mutateAsync({ type: media.type, id: media.id, deleteFiles, deleteDownloads });
                    toast.success(`« ${media.title} » supprimé`, {
                        description: deleteFiles ? "Les fichiers ont aussi été effacés du disque." : "Les fichiers sont restés sur le disque.",
                    });
                    router.push("/media");
                } catch (e) {
                    toast.error("Suppression impossible", { description: e instanceof Error ? e.message : String(e) });
                    // On relance l'erreur pour que la boîte reste ouverte.
                    throw e;
                }
            }}
        >
            <div className="space-y-2">
                <div className="flex items-start justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                    <Label htmlFor="delete-files" className="cursor-pointer leading-snug">
                        Effacer aussi les fichiers du disque
                        <span className="mt-1 block text-xs font-normal text-muted-foreground">Sinon, seuls les réglages {arr} sont supprimés.</span>
                    </Label>
                    <Switch
                        id="delete-files"
                        checked={deleteFiles}
                        onCheckedChange={setDeleteFiles}
                        className="data-[state=checked]:bg-red-500 data-[state=checked]:shadow-[0_0_14px_-2px_rgb(239_68_68/0.8)]"
                    />
                </div>
                <div className="flex items-start justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                    <Label htmlFor="delete-downloads" className="cursor-pointer leading-snug">
                        Nettoyer la file et l&apos;historique de téléchargement
                        <span className="mt-1 block text-xs font-normal text-muted-foreground">SABnzbd, torrents en cours, historique {arr}.</span>
                    </Label>
                    <Switch
                        id="delete-downloads"
                        checked={deleteDownloads}
                        onCheckedChange={setDeleteDownloads}
                        className="data-[state=checked]:bg-red-500 data-[state=checked]:shadow-[0_0_14px_-2px_rgb(239_68_68/0.8)]"
                    />
                </div>
            </div>
        </ConfirmDialog>
    );
}
