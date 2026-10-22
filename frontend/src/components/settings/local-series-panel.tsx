"use client";

/**
 * Réglages › Dossiers vidéo › Séries maison.
 * ----------------------------------------------------------------
 * Déclarer un dossier (Naruto Kai, One Pace…) comme une série : elle
 * apparaît dans la grille Séries de l'appli, avec ses saisons (sous-dossiers)
 * et ses épisodes (vidéos), comme une série Sonarr. Trois étapes : choisir
 * le dossier, la série officielle pour l'affiche (TMDB), le nom.
 */
import { useState, type FormEvent } from "react";
import { AlertTriangle, ChevronRight, Folder, Loader2, Pencil, Plus, Search, Trash2, Tv } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Panel } from "@/components/shared/panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { FormField } from "@/components/settings/form-field";
import { useDebounce } from "@/hooks/use-debounce";
import {
    decodeVideoToken,
    useCreateLocalSeries,
    useDeleteLocalSeries,
    useLocalSeries,
    useTmdbSeriesSearch,
    useUpdateLocalSeries,
    useVideoListing,
    type LocalSeries,
} from "@/hooks/use-local-series";
import { cn } from "@/lib/utils";

/** Sélecteur de dossier : on navigue dans les dossiers vidéo comme sur la TV. */
function FolderPicker({ onPick }: { onPick: (folder: { rootId: number; path: string; name: string }) => void }) {
    const [token, setToken] = useState<string | null>(null);
    const { data, isLoading, isError, error } = useVideoListing(token);
    const current = data?.crumbs.at(-1);
    return (
        <div className="space-y-2 rounded-lg border border-white/10 p-3">
            <div className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                <button type="button" className="hover:text-foreground" onClick={() => setToken(null)}>
                    Dossiers vidéo
                </button>
                {data?.crumbs.map((c) => (
                    <span key={c.token} className="flex items-center gap-1">
                        <ChevronRight className="h-3 w-3" />
                        <button type="button" className="hover:text-foreground" onClick={() => setToken(c.token)}>
                            {c.name}
                        </button>
                    </span>
                ))}
            </div>
            {isLoading ? (
                <TableSkeleton rows={3} />
            ) : isError ? (
                <p className="text-xs text-destructive">{error.message}</p>
            ) : (
                <ul className="max-h-56 overflow-y-auto">
                    {data?.folders.map((f) => (
                        <li key={f.token}>
                            <button
                                type="button"
                                onClick={() => setToken(f.token)}
                                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-white/5"
                            >
                                <Folder className="h-4 w-4 text-warning" />
                                <span className="flex-1 truncate">{f.name}</span>
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </button>
                        </li>
                    ))}
                    {data && data.folders.length === 0 && (
                        <li className="px-2 py-1.5 text-xs text-muted-foreground">
                            {token ? "Pas de sous-dossier." : "Aucun dossier vidéo : ajoute-en un ci-dessus."}
                        </li>
                    )}
                </ul>
            )}
            {token && current && (
                <div className="flex items-center justify-between gap-2 border-t border-white/10 pt-2">
                    <p className="truncate text-xs text-muted-foreground">
                        {data?.files.length ?? 0} vidéo(s) ici · {data?.folders.length ?? 0} sous-dossier(s)
                    </p>
                    <Button type="button" size="sm" onClick={() => onPick({ ...decodeVideoToken(token), name: current.name })}>
                        Choisir « {current.name} »
                    </Button>
                </div>
            )}
        </div>
    );
}

/** Recherche de la série officielle (affiche, fond, résumé). */
function TmdbPicker({ value, onChange }: { value: number | null; onChange: (id: number | null) => void }) {
    const [query, setQuery] = useState("");
    const debounced = useDebounce(query, 400);
    const { data, isFetching, error } = useTmdbSeriesSearch(debounced);
    return (
        <div className="space-y-2">
            <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Naruto" className="pl-8" />
            </div>
            {error && <p className="text-xs text-warning">{error.message}</p>}
            {isFetching && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
            <div className="flex gap-2 overflow-x-auto pb-1">
                {value !== null && (
                    <button type="button" onClick={() => onChange(null)} className="shrink-0 self-center text-xs text-muted-foreground hover:text-foreground">
                        Aucune
                    </button>
                )}
                {data?.map((hit) => (
                    <button
                        key={hit.tmdb_id}
                        type="button"
                        onClick={() => onChange(hit.tmdb_id)}
                        className={cn(
                            "w-20 shrink-0 rounded-md p-1 text-left ring-offset-2 ring-offset-background transition",
                            hit.tmdb_id === value ? "ring-2 ring-sky-400" : "opacity-80 hover:opacity-100",
                        )}
                    >
                        {hit.poster_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={hit.poster_url} alt="" className="aspect-[2/3] w-full rounded object-cover" />
                        ) : (
                            <div className="flex aspect-[2/3] w-full items-center justify-center rounded bg-white/5">
                                <Tv className="h-5 w-5 text-muted-foreground" />
                            </div>
                        )}
                        <p className="mt-1 truncate text-[11px]">{hit.title}</p>
                        <p className="text-[10px] text-muted-foreground">{hit.year ?? ""}</p>
                    </button>
                ))}
            </div>
        </div>
    );
}

export function LocalSeriesPanel() {
    const { data: series, isLoading, isError, error, refetch } = useLocalSeries();
    const create = useCreateLocalSeries();
    const update = useUpdateLocalSeries();
    const del = useDeleteLocalSeries();
    const [adding, setAdding] = useState(false);
    const [editing, setEditing] = useState<LocalSeries | null>(null);
    const [deleting, setDeleting] = useState<LocalSeries | null>(null);

    // Formulaire d'ajout
    const [folder, setFolder] = useState<{ rootId: number; path: string; name: string } | null>(null);
    const [title, setTitle] = useState("");
    const [badge, setBadge] = useState("Kai");
    const [tmdbId, setTmdbId] = useState<number | null>(null);

    const openAdd = () => {
        setFolder(null);
        setTitle("");
        setBadge("Kai");
        setTmdbId(null);
        setAdding(true);
    };

    const submitAdd = (e: FormEvent) => {
        e.preventDefault();
        if (!folder || !title.trim()) return;
        create.mutate(
            { root_id: folder.rootId, path: folder.path, title: title.trim(), badge: badge.trim(), tmdb_id: tmdbId },
            {
                onSuccess: (s) => {
                    toast.success(`« ${s.title} » ajoutée : ${s.seasons} saison(s), ${s.episodes} épisode(s)`);
                    setAdding(false);
                },
                onError: (err) => toast.error("Ajout impossible", { description: err.message }),
            },
        );
    };

    return (
        <>
            <Panel
                title="Séries maison"
                icon={Tv}
                iconClassName="text-primary"
                action={
                    <Button size="sm" onClick={openAdd} disabled={isLoading}>
                        <Plus />
                        Déclarer une série
                    </Button>
                }
                bodyClassName="space-y-4"
            >
                <p className="text-xs leading-relaxed text-muted-foreground">
                    Pour les montages sans fiche officielle (Naruto Kai, One Pace…) : le dossier apparaît dans la grille{" "}
                    <strong>Séries</strong> de l&apos;appli, comme une série Sonarr. Sous-dossiers = saisons (arcs), vidéos = épisodes
                    (numéro lu dans le nom : <code>Naruto Kai - 015</code>). Les <code>tvshow.nfo</code>, <code>.nfo</code> d&apos;épisode et{" "}
                    <code>poster.jpg</code> posés dans le dossier (Jellyfin, OnePacerr) sont repris.
                </p>
                {isLoading ? (
                    <TableSkeleton rows={2} />
                ) : isError ? (
                    <ErrorState error={error} onRetry={() => refetch()} />
                ) : series && series.length === 0 ? (
                    <p className="rounded-lg border border-dashed border-white/10 p-4 text-sm text-muted-foreground">Aucune série maison.</p>
                ) : (
                    <ul className="divide-y divide-white/[0.05]">
                        {series?.map((s) => (
                            <li key={s.id} className="flex items-center gap-3 py-3">
                                {s.poster_url && s.poster_url.startsWith("http") ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={s.poster_url} alt="" className="h-14 w-10 shrink-0 rounded object-cover" />
                                ) : (
                                    <div className="flex h-14 w-10 shrink-0 items-center justify-center rounded bg-white/5">
                                        <Tv className="h-4 w-4 text-muted-foreground" />
                                    </div>
                                )}
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-semibold">
                                        {s.title}
                                        {s.badge && <span className="ml-2 rounded bg-primary/20 px-1.5 py-0.5 text-[10px] text-sky-200">{s.badge}</span>}
                                    </p>
                                    <p className="truncate text-xs text-muted-foreground">
                                        {s.seasons} saison(s) · {s.episodes} épisode(s) · <span className="font-mono">{s.path || "/"}</span>
                                    </p>
                                    {!s.available && (
                                        <p className="mt-1 flex items-center gap-1 text-xs text-warning">
                                            <AlertTriangle className="h-3.5 w-3.5" />
                                            Dossier introuvable sur le NAS
                                        </p>
                                    )}
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => setEditing(s)} aria-label={`Modifier ${s.title}`}>
                                    <Pencil />
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => setDeleting(s)} aria-label={`Retirer ${s.title}`}>
                                    <Trash2 />
                                </Button>
                            </li>
                        ))}
                    </ul>
                )}
            </Panel>

            <Dialog open={adding} onOpenChange={setAdding}>
                <DialogContent className="max-w-xl">
                    <DialogHeader>
                        <DialogTitle>Déclarer une série maison</DialogTitle>
                        <DialogDescription>Le dossier de la série, puis la série officielle dont on emprunte l&apos;affiche.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={submitAdd} className="space-y-4">
                        <FormField id="ls-folder" label="1. Dossier de la série">
                            {folder ? (
                                <div className="flex items-center justify-between gap-2 rounded-lg border border-white/10 px-3 py-2">
                                    <span className="truncate font-mono text-xs">{folder.path || "/"}</span>
                                    <Button type="button" variant="ghost" size="sm" onClick={() => setFolder(null)}>
                                        Changer
                                    </Button>
                                </div>
                            ) : (
                                <FolderPicker
                                    onPick={(f) => {
                                        setFolder(f);
                                        if (!title) setTitle(f.name);
                                    }}
                                />
                            )}
                        </FormField>
                        <FormField id="ls-tmdb" label="2. Série officielle (affiche, fond, résumé)" hint="Facultatif : Naruto pour Naruto Kai. Un poster.jpg dans le dossier reste prioritaire.">
                            <TmdbPicker value={tmdbId} onChange={setTmdbId} />
                        </FormField>
                        <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
                            <FormField id="ls-title" label="3. Nom affiché">
                                <Input id="ls-title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} placeholder="Naruto Kai" />
                            </FormField>
                            <FormField id="ls-badge" label="Pastille">
                                <Input id="ls-badge" value={badge} maxLength={20} onChange={(e) => setBadge(e.target.value)} placeholder="Kai" />
                            </FormField>
                        </div>
                        <div className="flex justify-end">
                            <Button type="submit" disabled={create.isPending || !folder || !title.trim()}>
                                {create.isPending ? <Loader2 className="animate-spin" /> : null}
                                Ajouter à la grille Séries
                            </Button>
                        </div>
                    </form>
                </DialogContent>
            </Dialog>

            <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Modifier « {editing?.title} »</DialogTitle>
                        <DialogDescription>Nom, pastille et série officielle (affiche).</DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <EditForm
                            key={editing.id}
                            series={editing}
                            pending={update.isPending}
                            onSubmit={(values) =>
                                update.mutate(
                                    { id: editing.id, ...values },
                                    {
                                        onSuccess: () => {
                                            toast.success("Série enregistrée");
                                            setEditing(null);
                                        },
                                        onError: (err) => toast.error("Enregistrement impossible", { description: err.message }),
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
                title={`Retirer « ${deleting?.title ?? ""} » ?`}
                description="Elle disparaît de la grille Séries ; les vidéos restent dans l'écran Vidéos, avec leur vu / reprise."
                destructive
                confirmLabel="Retirer"
                onConfirm={() =>
                    deleting
                        ? del.mutateAsync(deleting.id).then(
                              () => {
                                  toast.success("Série retirée");
                                  setDeleting(null);
                              },
                              (err: Error) => toast.error("Retrait impossible", { description: err.message }),
                          )
                        : undefined
                }
            />
        </>
    );
}

function EditForm({
    series,
    pending,
    onSubmit,
}: {
    series: LocalSeries;
    pending: boolean;
    onSubmit: (values: { title: string; badge: string; tmdb_id?: number | null }) => void;
}) {
    const [title, setTitle] = useState(series.title);
    const [badge, setBadge] = useState(series.badge);
    const [tmdbId, setTmdbId] = useState<number | null>(series.tmdb_id);
    const submit = (e: FormEvent) => {
        e.preventDefault();
        if (!title.trim()) return;
        onSubmit({ title: title.trim(), badge: badge.trim(), ...(tmdbId !== series.tmdb_id ? { tmdb_id: tmdbId } : {}) });
    };
    return (
        <form onSubmit={submit} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_140px]">
                <FormField id="ls-edit-title" label="Nom affiché">
                    <Input id="ls-edit-title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
                </FormField>
                <FormField id="ls-edit-badge" label="Pastille">
                    <Input id="ls-edit-badge" value={badge} maxLength={20} onChange={(e) => setBadge(e.target.value)} />
                </FormField>
            </div>
            <FormField id="ls-edit-tmdb" label="Série officielle" hint={series.tmdb_id ? `Actuelle : TMDB ${series.tmdb_id}` : "Aucune pour l'instant"}>
                <TmdbPicker value={tmdbId} onChange={setTmdbId} />
            </FormField>
            <div className="flex justify-end">
                <Button type="submit" disabled={pending || !title.trim()}>
                    {pending ? <Loader2 className="animate-spin" /> : null}
                    Enregistrer
                </Button>
            </div>
        </form>
    );
}
