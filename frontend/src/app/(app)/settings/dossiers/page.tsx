"use client";

/**
 * Paramètres → Dossiers vidéo.
 * ----------------------------------------------------------------
 * Dossiers du NAS montrés dans l'écran « Vidéos » de l'appli Android : on
 * les parcourt comme un explorateur de fichiers (dossiers, vidéos,
 * sous-titres posés à côté). Pour les vidéos sans fiche officielle (mangas
 * « Kai », montages, vidéos perso) que Radarr, Sonarr et Jellyfin ignorent.
 * Retirer un dossier ne supprime rien sur le disque.
 *
 * Le chemin est celui vu DEPUIS LE CONTENEUR ArrMada (comme un point de
 * montage NFS vu depuis le client, pas le chemin d'export du serveur). Sur
 * Synology, le réflexe est de saisir « /volume1/mangas » : le serveur refuse
 * alors en donnant la ligne de volume à ajouter au docker-compose.yml et le
 * chemin à saisir ensuite, affichés ici avec un bouton « Copier ».
 */
import { useState, type FormEvent } from "react";
import { AlertTriangle, Copy, CornerDownLeft, FolderOpen, Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Panel } from "@/components/shared/panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { FormField } from "@/components/settings/form-field";
import { LocalSeriesPanel } from "@/components/settings/local-series-panel";
import { copyText } from "@/components/media-detail/labels";
import {
    MAX_VIDEO_ROOTS,
    useCreateVideoRoot,
    useDeleteVideoRoot,
    useUpdateVideoRoot,
    useVideoRootBases,
    useVideoRoots,
    videoRootHint,
    type VideoRoot,
} from "@/hooks/use-video-roots";

/**
 * Refus du serveur avec aide : la ligne à ajouter au service arrmada du
 * docker-compose.yml (bouton Copier) et le chemin à saisir une fois le
 * conteneur relancé (bouton qui remplit le champ).
 */
function MountHint({ error, onUsePath }: { error: unknown; onUsePath: (path: string) => void }) {
    const hint = videoRootHint(error);
    if (!hint) return null;
    const copy = async (text: string) => {
        if (await copyText(text)) toast.success("Ligne copiée", { description: text });
        else toast.error("Copie impossible", { description: "Sélectionne la ligne et copie-la à la main." });
    };
    return (
        <div data-testid="mount-hint" role="alert" className="space-y-3 rounded-xl border border-warning/25 bg-warning/10 p-3 text-xs text-warning">
            <p className="flex items-start gap-2 leading-relaxed">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 break-words">{hint.message}</span>
            </p>
            {hint.volume_line && (
                <div className="space-y-1.5">
                    <p className="font-medium text-foreground">
                        1. Ajoute cette ligne sous <code>volumes:</code> du service <code>arrmada</code>, puis relance le conteneur :
                    </p>
                    <div className="flex items-center gap-2">
                        <code
                            data-testid="volume-line"
                            className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap rounded-lg bg-background/60 px-2.5 py-1.5 font-mono text-[11px] text-foreground">
                            {hint.volume_line}
                        </code>
                        <Button type="button" size="sm" variant="outline" onClick={() => copy(hint.volume_line!)}>
                            <Copy />
                            Copier
                        </Button>
                    </div>
                    <p className="text-muted-foreground">
                        Puis : <code>docker compose up -d arrmada</code> (ou « Action › Construire » dans Container Manager).
                    </p>
                </div>
            )}
            {hint.container_path && (
                <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium text-foreground">
                        {hint.volume_line ? "2. " : ""}Chemin à saisir ensuite : <code className="font-mono">{hint.container_path}</code>
                    </p>
                    <Button type="button" size="sm" variant="outline" onClick={() => onUsePath(hint.container_path!)}>
                        <CornerDownLeft />
                        Utiliser ce chemin
                    </Button>
                </div>
            )}
        </div>
    );
}

/** Formulaire commun (ajout, modification) : libellé et chemin sur le serveur. */
function RootForm({
    initial,
    submitLabel,
    pending,
    bases,
    error,
    onSubmit,
}: {
    initial: { name: string; path: string };
    submitLabel: string;
    pending: boolean;
    /** Bases autorisées (VIDEO_ALLOWED_BASE), pour l'aide et l'exemple. */
    bases: string[];
    /** Dernière erreur du serveur : son aide (ligne de volume) s'affiche ici. */
    error: unknown;
    onSubmit: (values: { name: string; path: string }) => void;
}) {
    const [name, setName] = useState(initial.name);
    const [path, setPath] = useState(initial.path);
    const valid = name.trim() !== "" && path.trim().startsWith("/");
    const example = `${bases[0] ?? "/mnt/user"}/medias/mangas-kai`;
    const submit = (e: FormEvent) => {
        e.preventDefault();
        if (valid) onSubmit({ name: name.trim(), path: path.trim() });
    };
    return (
        <form onSubmit={submit} className="space-y-4">
            <FormField id="root-name" label="Nom affiché sur la TV">
                <Input id="root-name" value={name} maxLength={60} onChange={(e) => setName(e.target.value)} placeholder="Mangas Kai" autoFocus />
            </FormField>
            <FormField
                id="root-path"
                label="Chemin sur le serveur"
                hint={`Tel que le voit le conteneur ArrMada (pas le chemin du NAS), sous ${bases.join(" ou ") || "n'importe quel dossier"} (ex. ${example}).`}
            >
                <Input
                    id="root-path"
                    value={path}
                    maxLength={500}
                    onChange={(e) => setPath(e.target.value)}
                    placeholder={example}
                    className="font-mono text-xs"
                />
            </FormField>
            <MountHint error={error} onUsePath={setPath} />
            <div className="flex justify-end">
                <Button type="submit" disabled={pending || !valid}>
                    {pending ? <Loader2 className="animate-spin" /> : null}
                    {submitLabel}
                </Button>
            </div>
        </form>
    );
}

export default function VideoRootsPage() {
    const { data: roots, isLoading, isError, error, refetch } = useVideoRoots();
    const { data: bases = ["/mnt/user"] } = useVideoRootBases();
    const create = useCreateVideoRoot();
    const update = useUpdateVideoRoot();
    const del = useDeleteVideoRoot();
    const [adding, setAdding] = useState(false);
    const [editing, setEditing] = useState<VideoRoot | null>(null);
    const [deleting, setDeleting] = useState<VideoRoot | null>(null);
    const full = (roots?.length ?? 0) >= MAX_VIDEO_ROOTS;

    return (
        <div className="space-y-6">
            <Panel
                title="Dossiers vidéo"
                icon={FolderOpen}
                iconClassName="text-warning"
                action={
                    <Button
                        size="sm"
                        onClick={() => {
                            create.reset(); // pas d'aide d'un essai précédent
                            setAdding(true);
                        }}
                        disabled={full || isLoading}
                    >
                        <Plus />
                        Ajouter
                    </Button>
                }
                bodyClassName="space-y-4"
            >
                <p className="text-xs leading-relaxed text-muted-foreground">
                    L&apos;écran « Vidéos » de l&apos;appli Android (TV, téléphone, tablette) parcourt ces dossiers comme un explorateur de
                    fichiers : pour les vidéos sans fiche officielle — mangas « Kai », montages, vidéos perso — que Radarr, Sonarr et
                    Jellyfin ne rangent pas. Lecture du fichier d&apos;origine, vu / reprise par profil, sous-titres posés à côté (
                    <code>Episode 01.fr.srt</code>). Rien n&apos;est modifié sur le disque.
                </p>
                {isLoading ? (
                    <TableSkeleton rows={3} />
                ) : isError ? (
                    <ErrorState error={error} onRetry={() => refetch()} />
                ) : roots && roots.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-white/10 p-4 text-sm text-muted-foreground">
                        Aucun dossier pour l&apos;instant : ajoute par exemple <code>{bases[0] ?? "/mnt/user"}/medias/mangas-kai</code>.
                    </p>
                ) : (
                    <ul className="divide-y divide-white/[0.05]">
                        {roots?.map((r) => (
                            <li key={r.id} className="flex items-center gap-3 py-3">
                                <FolderOpen className="h-5 w-5 shrink-0 text-warning" />
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-semibold">{r.name}</p>
                                    <p className="truncate font-mono text-xs text-muted-foreground">{r.path}</p>
                                    {!r.available && (
                                        <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                                            <AlertTriangle className="h-3.5 w-3.5" />
                                            Introuvable sur le serveur (partage démonté ?)
                                        </p>
                                    )}
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                        update.reset();
                                        setEditing(r);
                                    }}
                                    aria-label={`Modifier ${r.name}`}
                                >
                                    <Pencil />
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => setDeleting(r)} aria-label={`Retirer ${r.name}`}>
                                    <Trash2 />
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
                {full && <p className="text-xs text-muted-foreground">{MAX_VIDEO_ROOTS} dossiers au plus.</p>}
            </Panel>

            {/* Séries maison : un dossier vu comme une série (Naruto Kai, One Pace…) */}
            <LocalSeriesPanel />

            <Dialog open={adding} onOpenChange={setAdding}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Nouveau dossier vidéo</DialogTitle>
                        <DialogDescription>Il apparaît aussitôt dans l&apos;écran « Vidéos » des TV et téléphones.</DialogDescription>
                    </DialogHeader>
                    <RootForm
                        initial={{ name: "", path: `${bases[0] ?? "/mnt/user"}/` }}
                        submitLabel="Ajouter"
                        pending={create.isPending}
                        bases={bases}
                        error={create.error}
                        onSubmit={(values) =>
                            create.mutate(values, {
                                onSuccess: (r) => {
                                    toast.success(`Dossier « ${r.name} » ajouté`);
                                    setAdding(false);
                                },
                                // Avec une aide (ligne de volume), elle s'affiche dans le formulaire
                                onError: (e) => videoRootHint(e) || toast.error("Ajout impossible", { description: e.message }),
                            })
                        }
                    />
                </DialogContent>
            </Dialog>

            <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Modifier le dossier</DialogTitle>
                        <DialogDescription>Le vu / la reprise suivent le fichier : déplacer le dossier les remet à zéro.</DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <RootForm
                            key={editing.id}
                            initial={{ name: editing.name, path: editing.path }}
                            submitLabel="Enregistrer"
                            pending={update.isPending}
                            bases={bases}
                            error={update.error}
                            onSubmit={(values) =>
                                update.mutate(
                                    { id: editing.id, ...values },
                                    {
                                        onSuccess: () => {
                                            toast.success("Dossier enregistré");
                                            setEditing(null);
                                        },
                                        onError: (e) =>
                                            videoRootHint(e) || toast.error("Enregistrement impossible", { description: e.message }),
                                    },
                                )
                            }
                        />
                    )}
                </DialogContent>
            </Dialog>

            <ConfirmDialog
                open={deleting !== null}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Retirer « ${deleting?.name ?? ""} » ?`}
                description="Il disparaît de l'écran Vidéos. Rien n'est supprimé sur le disque."
                destructive
                confirmLabel="Retirer"
                onConfirm={() =>
                    deleting
                        ? del.mutateAsync(deleting.id).then(
                              () => {
                                  toast.success("Dossier retiré");
                                  setDeleting(null);
                              },
                              (e: Error) => toast.error("Retrait impossible", { description: e.message }),
                          )
                        : undefined
                }
            />
        </div>
    );
}
