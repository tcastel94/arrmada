"use client";

/**
 * Déplacement d'un média vers un autre dossier racine (Radarr / Sonarr
 * déplacent physiquement les fichiers sur le disque).
 * Le composant est remonté à chaque ouverture (prop `key` côté page) :
 * le formulaire repart toujours du chemin actuel.
 */
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { ArrowDown, FolderInput, Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { useMediaRootFolders, useUpdateMediaPath, type MediaDetail } from "@/hooks/use-media";
import { formatBytes } from "@/lib/format";
import { basename } from "./labels";

const joinPath = (root: string, folder: string) => (root.endsWith("/") ? `${root}${folder}` : `${root}/${folder}`);

export function MoveMediaDialog({
    media,
    open,
    onOpenChange,
}: {
    media: MediaDetail;
    open: boolean;
    onOpenChange: (v: boolean) => void;
}) {
    const arr = media.type === "movie" ? "Radarr" : "Sonarr";
    const rootFolders = useMediaRootFolders(media.type, String(media.id), open);
    const updatePath = useUpdateMediaPath();

    // Dossier racine qui contient le chemin actuel (présélectionné).
    const currentRoot = useMemo(
        () =>
            rootFolders.data
                ?.filter((rf) => media.path.startsWith(rf.path.replace(/\/+$/, "")))
                .sort((a, b) => b.path.length - a.path.length)[0]?.path,
        [rootFolders.data, media.path],
    );
    const [root, setRoot] = useState("");
    const [folder, setFolder] = useState(basename(media.path));

    // Présélection dès que la liste arrive.
    useEffect(() => {
        if (!root && rootFolders.data?.length) setRoot(currentRoot ?? rootFolders.data[0].path);
    }, [root, currentRoot, rootFolders.data]);

    const target = root && folder.trim() ? joinPath(root, folder.trim()) : "";
    const unchanged = target.replace(/\/+$/, "") === media.path.replace(/\/+$/, "");

    const submit = () => {
        if (!root) return toast.error("Choisis un dossier racine.");
        if (!folder.trim()) return toast.error("Indique un nom de dossier.");
        updatePath.mutate(
            { type: media.type, id: String(media.id), new_path: target },
            {
                onSuccess: () => {
                    toast.success("Déplacement lancé", {
                        description: `${arr} transfère les fichiers en arrière-plan vers ${target}.`,
                    });
                    onOpenChange(false);
                },
                onError: (err) => toast.error("Déplacement impossible", { description: err.message }),
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !updatePath.isPending && onOpenChange(o)}>
            <DialogContent className="sm:max-w-[520px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <FolderInput className="h-4 w-4" />
                        </span>
                        Déplacer les fichiers
                    </DialogTitle>
                    <DialogDescription>
                        Choisis un nouvel emplacement : {arr} déplacera physiquement tous les fichiers sur le disque.
                    </DialogDescription>
                </DialogHeader>

                {rootFolders.isLoading ? (
                    <div className="space-y-3">
                        <Shimmer className="h-9 w-full" />
                        <Shimmer className="h-9 w-full" />
                        <Shimmer className="h-16 w-full" />
                    </div>
                ) : rootFolders.isError ? (
                    <ErrorState compact error={rootFolders.error} onRetry={() => rootFolders.refetch()} title="Dossiers racine indisponibles" />
                ) : !rootFolders.data?.length ? (
                    <EmptyState compact icon={FolderInput} title="Aucun dossier racine" description={`Ajoute un dossier racine dans ${arr} pour pouvoir déplacer ce média.`} />
                ) : (
                    <div className="space-y-4">
                        <div className="space-y-1.5">
                            <Label htmlFor="move-root">Dossier racine cible</Label>
                            <Select value={root} onValueChange={setRoot}>
                                <SelectTrigger id="move-root">
                                    <SelectValue placeholder="Choisir un dossier racine…" />
                                </SelectTrigger>
                                <SelectContent>
                                    {rootFolders.data.map((rf) => (
                                        <SelectItem key={rf.path} value={rf.path} disabled={!rf.accessible}>
                                            {rf.path} · {rf.accessible ? `${formatBytes(rf.freeSpace)} libres` : "inaccessible"}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="move-folder">Nom du dossier de destination</Label>
                            <Input id="move-folder" value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="Nom du dossier…" />
                        </div>
                        <div className="space-y-2 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                            <p className="eyebrow">Chemin actuel</p>
                            <code className="block break-all font-mono text-xs text-muted-foreground">{media.path}</code>
                            <ArrowDown className="h-3.5 w-3.5 text-primary" aria-hidden />
                            <p className="eyebrow">Nouveau chemin</p>
                            <code className="block break-all font-mono text-xs text-primary">{target || "—"}</code>
                        </div>
                    </div>
                )}

                <DialogFooter>
                    <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={updatePath.isPending}>
                        Annuler
                    </Button>
                    <Button onClick={submit} disabled={updatePath.isPending || !target || unchanged}>
                        {updatePath.isPending && <Loader2 className="animate-spin" />}
                        {updatePath.isPending ? "Déplacement…" : "Déplacer les fichiers"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
