"use client";

/**
 * Même version audio pour toute une sélection de la médiathèque.
 * ----------------------------------------------------------------
 * Cas d'usage : filtrer « Animation » / « Familial », tout sélectionner, puis
 * « Version » → VF, doublage France. Un seul appel serveur : les profils
 * manquants sont créés, les titres basculés d'un coup.
 *
 * Par défaut la qualité reste celle de chaque titre (un film en 4K reste en
 * 4K) et rien n'est retéléchargé : la recherche est une case à cocher, car
 * lancer 50 recherches d'un coup sollicite beaucoup les indexeurs.
 * Pas de remplacement forcé ici (trop destructeur en lot) : il se fait titre
 * par titre, depuis la fiche.
 */
import { useState } from "react";
import { toast } from "sonner";
import { Languages, Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import type { MediaItem } from "@/hooks/use-media";
import { useSetMediaVersionBulk } from "@/hooks/use-media-version";
import { plural } from "@/lib/format";
import { VersionPicker, type PickerValue } from "@/components/media-detail/version-picker";
import { versionLabel } from "@/components/media-detail/version-options";

export function BulkVersionDialog({
    items,
    open,
    onOpenChange,
    onDone,
}: {
    items: MediaItem[];
    open: boolean;
    onOpenChange: (v: boolean) => void;
    /** Appelé après un succès (ex : quitter le mode sélection). */
    onDone?: () => void;
}) {
    const save = useSetMediaVersionBulk();
    const [value, setValue] = useState<PickerValue>({ language: null, quality: null, dub: "france" });
    const [search, setSearch] = useState(false);

    const movies = items.filter((i) => i.type === "movie").length;
    const series = items.length - movies;
    const summary = [movies > 0 && plural(movies, "film"), series > 0 && plural(series, "série")].filter(Boolean).join(" et ");

    const submit = () => {
        if (!value.language) return;
        const language = value.language;
        const dub = language === "vf" ? value.dub : "any";
        save.mutate(
            {
                items: items.map((i) => ({ type: i.type, id: Number(i.external_id) })),
                language,
                quality: value.quality,
                dub,
                action: search ? "search" : "none",
            },
            {
                onSuccess: (r) => {
                    const parts = [
                        r.changed === r.total ? `${plural(r.changed, "titre modifié", "titres modifiés")}` : `${r.changed} modifié${r.changed > 1 ? "s" : ""} sur ${r.total}`,
                        r.created_profiles.length > 0 && `${plural(r.created_profiles.length, "profil créé", "profils créés")}`,
                        r.searched > 0 ? `${plural(r.searched, "recherche lancée", "recherches lancées")}` : "rien n'est retéléchargé pour l'instant",
                    ].filter(Boolean);
                    toast.success(`Version ${versionLabel({ language, dub, quality: value.quality })}`, { description: `${parts.join(" · ")}.` });
                    if (r.warnings.length) toast.warning("Profil créé avec des réserves", { description: r.warnings.slice(0, 3).join(" · ") });
                    onOpenChange(false);
                    onDone?.();
                },
                onError: (e) => toast.error("Changement de version impossible", { description: e.message }),
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !save.isPending && onOpenChange(o)}>
            <DialogContent className="sm:max-w-[560px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 pr-6">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <Languages className="h-4 w-4" />
                        </span>
                        Version de {summary}
                    </DialogTitle>
                    <DialogDescription>
                        La même version audio pour toute la sélection. Les autres titres de ta médiathèque ne changent pas.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-5 py-1">
                    <VersionPicker value={value} onChange={setValue} allowKeepQuality />

                    <div className="flex items-start justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                        <Label htmlFor="bulk-version-search" className="text-sm leading-snug">
                            Lancer la recherche maintenant
                            <span className="mt-1 block text-xs font-normal text-muted-foreground">
                                Les fichiers déjà présents ne sont remplacés que si une meilleure release existe. Sinon, le réglage servira aux prochaines
                                mises à niveau automatiques.
                            </span>
                        </Label>
                        <Switch id="bulk-version-search" checked={search} onCheckedChange={setSearch} />
                    </div>

                    <p className="line-clamp-2 text-xs text-muted-foreground">
                        {items
                            .slice(0, 6)
                            .map((i) => i.title)
                            .join(" · ")}
                        {items.length > 6 && ` · +${items.length - 6}`}
                    </p>
                </div>

                <DialogFooter>
                    <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={save.isPending}>
                        Annuler
                    </Button>
                    <Button onClick={submit} disabled={save.isPending || !value.language || items.length === 0}>
                        {save.isPending && <Loader2 className="animate-spin" />}
                        Appliquer à {plural(items.length, "titre")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
