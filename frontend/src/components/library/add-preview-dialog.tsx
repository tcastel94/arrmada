"use client";

/**
 * Aperçu d'un titre à ajouter : grande affiche, résumé complet, note,
 * lien vers la fiche TMDB / TheTVDB et bouton d'ajout.
 * (Porté de l'ancienne page /requests, qui montrait le résumé et le lien
 * externe dans son autocomplétion.)
 */
/* eslint-disable @next/next/no-img-element */
import { ExternalLink, Film, Loader2, Plus, Star, Tv, Check } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MediaThumb } from "./media-thumb";
import { externalLink, useAdder, type AddableItem } from "./adder";

export function AddPreviewDialog({
    item,
    onOpenChange,
    onShowTracking,
}: {
    item: AddableItem | null;
    onOpenChange: (open: boolean) => void;
    onShowTracking?: () => void;
}) {
    const { add, stateOf } = useAdder();
    const state = item ? stateOf(item.key) : "idle";
    const link = item ? externalLink(item) : null;
    const TypeIcon = item?.type === "series" ? Tv : Film;

    return (
        <Dialog open={!!item} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-2xl overflow-hidden p-0">
                {item && (
                    <div className="relative">
                        {/* Fond : l'affiche floutée, pour l'ambiance */}
                        {item.poster_url && (
                            <img
                                src={item.poster_url}
                                alt=""
                                aria-hidden
                                className="pointer-events-none absolute inset-0 h-full w-full scale-125 object-cover opacity-25 blur-3xl"
                            />
                        )}
                        <div className="relative flex flex-col gap-5 p-6 sm:flex-row">
                            <MediaThumb
                                src={item.poster_url}
                                alt={item.title}
                                type={item.type}
                                className="h-52 w-36 self-center rounded-2xl shadow-[0_24px_60px_-20px_rgba(0,0,0,0.9)] sm:self-start"
                            />
                            <div className="min-w-0 flex-1 space-y-4">
                                <DialogHeader className="space-y-2 pr-6 text-left">
                                    <DialogTitle className="text-xl leading-tight">{item.title}</DialogTitle>
                                    <DialogDescription asChild>
                                        <div className="flex flex-wrap items-center gap-1.5 text-xs">
                                            <span className="inline-flex items-center gap-1 rounded-full bg-white/[0.06] px-2 py-0.5 ring-1 ring-white/10">
                                                <TypeIcon className="h-3 w-3" />
                                                {item.type === "series" ? "Série" : "Film"}
                                            </span>
                                            {item.year && <span className="rounded-full bg-white/[0.06] px-2 py-0.5 tabular-nums ring-1 ring-white/10">{item.year}</span>}
                                            {item.rating && (
                                                <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-300 ring-1 ring-amber-500/25">
                                                    <Star className="h-3 w-3 fill-current" />
                                                    {item.rating.toFixed(1)}
                                                </span>
                                            )}
                                            <span className="text-muted-foreground">→ {item.type === "series" ? "Sonarr" : "Radarr"}</span>
                                        </div>
                                    </DialogDescription>
                                </DialogHeader>

                                <p className="max-h-48 overflow-y-auto pr-1 text-sm leading-relaxed text-muted-foreground">
                                    {item.overview || "Pas de résumé disponible pour ce titre."}
                                </p>

                                <div className="flex flex-wrap items-center gap-2">
                                    {item.in_library ? (
                                        <span className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300 ring-1 ring-emerald-500/25">
                                            <Check className="h-4 w-4" /> Déjà dans ta bibliothèque
                                        </span>
                                    ) : state === "added" ? (
                                        <>
                                            <span className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300 ring-1 ring-emerald-500/25">
                                                <Check className="h-4 w-4" /> Ajouté — recherche lancée
                                            </span>
                                            {onShowTracking && (
                                                <Button variant="ghost" onClick={onShowTracking}>
                                                    Voir le suivi
                                                </Button>
                                            )}
                                        </>
                                    ) : (
                                        <Button onClick={() => add(item)} disabled={state === "adding"} className={cn("min-w-[11rem]")}>
                                            {state === "adding" ? <Loader2 className="animate-spin" /> : <Plus />}
                                            {state === "adding" ? "Ajout en cours…" : `Ajouter à ${item.type === "series" ? "Sonarr" : "Radarr"}`}
                                        </Button>
                                    )}
                                    {link && (
                                        <Button variant="outline" asChild>
                                            <a href={link.href} target="_blank" rel="noreferrer noopener">
                                                Fiche {link.label}
                                                <ExternalLink />
                                            </a>
                                        </Button>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
