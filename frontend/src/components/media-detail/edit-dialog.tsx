"use client";

/**
 * Édition d'un média dans Radarr / Sonarr : surveillance, profil de
 * qualité, disponibilité minimale (film) / type de série, tags.
 * ----------------------------------------------------------------
 * Corrigé :
 *  - l'état était initialisé une seule fois → valeurs périmées à la
 *    réouverture. La page remonte ce composant (prop `key`) à chaque
 *    ouverture, donc le formulaire repart toujours des valeurs actuelles ;
 *  - options en cours de chargement / en erreur gérées (squelettes,
 *    Réessayer, Enregistrer désactivé) ;
 *  - <select>/<input> natifs → Select / Input / Label shadcn associés.
 */
import { useState } from "react";
import { toast } from "sonner";
import { Check, Loader2, Pencil, Plus } from "lucide-react";
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
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import {
    useCreateTag,
    useMediaEditOptions,
    useUpdateMedia,
    type MediaDetail,
    type MediaEditPayload,
} from "@/hooks/use-media";
import { MOVIE_AVAILABILITY, SERIES_TYPES } from "./labels";

export function EditMediaDialog({
    media,
    open,
    onOpenChange,
}: {
    media: MediaDetail;
    open: boolean;
    onOpenChange: (v: boolean) => void;
}) {
    const type = media.type;
    const isMovie = type === "movie";
    const arr = isMovie ? "Radarr" : "Sonarr";
    const options = useMediaEditOptions(type, open);
    const updateMedia = useUpdateMedia();
    const createTag = useCreateTag();

    // Valeurs initiales = état actuel du média (le composant est remonté à chaque ouverture).
    const [monitored, setMonitored] = useState<boolean>(media.monitored);
    const [qualityProfileId, setQualityProfileId] = useState<string>(
        media.quality_profile_id != null ? String(media.quality_profile_id) : "",
    );
    const [tags, setTags] = useState<number[]>(media.tags ?? []);
    const [availability, setAvailability] = useState<string>(
        MOVIE_AVAILABILITY.find((o) => o.value.toLowerCase() === (media.minimum_availability ?? "").toLowerCase())?.value ?? "released",
    );
    const [seriesType, setSeriesType] = useState<string>(media.series_type || "standard");
    const [newTag, setNewTag] = useState("");

    const ids = {
        monitored: `edit-monitored-${media.id}`,
        profile: `edit-profile-${media.id}`,
        extra: `edit-extra-${media.id}`,
        tag: `edit-newtag-${media.id}`,
    };

    const toggleTag = (id: number) => setTags((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));

    const handleAddTag = () => {
        const label = newTag.trim();
        if (!label) return;
        createTag.mutate(
            { type, label },
            {
                onSuccess: (tag) => {
                    setTags((prev) => [...prev, tag.id]);
                    setNewTag("");
                    toast.success(`Tag « ${tag.label} » créé`);
                },
                onError: (e) => toast.error("Création du tag impossible", { description: e.message }),
            },
        );
    };

    const handleSave = () => {
        const payload: MediaEditPayload = { monitored, tags };
        if (qualityProfileId) payload.quality_profile_id = Number(qualityProfileId);
        if (isMovie) payload.minimum_availability = availability;
        else payload.series_type = seriesType;

        updateMedia.mutate(
            { type, id: media.id, data: payload },
            {
                onSuccess: () => {
                    toast.success(`Modifications enregistrées dans ${arr}`);
                    onOpenChange(false);
                },
                onError: (e) => toast.error("Enregistrement impossible", { description: e.message }),
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !updateMedia.isPending && onOpenChange(o)}>
            <DialogContent className="sm:max-w-[520px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 pr-6">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <Pencil className="h-4 w-4" />
                        </span>
                        <span className="truncate">Éditer « {media.title} »</span>
                    </DialogTitle>
                    <DialogDescription>
                        Modifie les réglages {isMovie ? "du film" : "de la série"} directement dans {arr}.
                    </DialogDescription>
                </DialogHeader>

                {options.isError ? (
                    <ErrorState compact error={options.error} onRetry={() => options.refetch()} title={`Options ${arr} indisponibles`} />
                ) : (
                    <div className="space-y-5 py-1">
                        {/* Surveillance */}
                        <div className="flex items-center justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                            <div>
                                <Label htmlFor={ids.monitored}>Surveillé</Label>
                                <p className="mt-1 text-xs text-muted-foreground">
                                    {isMovie ? `${arr} cherche et met à niveau le film automatiquement.` : `${arr} cherche les nouveaux épisodes automatiquement.`}
                                </p>
                            </div>
                            <Switch id={ids.monitored} checked={monitored} onCheckedChange={setMonitored} />
                        </div>

                        {/* Profil de qualité */}
                        <div className="space-y-1.5">
                            <Label htmlFor={ids.profile}>Profil de qualité</Label>
                            {options.isLoading ? (
                                <Shimmer className="h-9 w-full" />
                            ) : (
                                <Select value={qualityProfileId} onValueChange={setQualityProfileId}>
                                    <SelectTrigger id={ids.profile}>
                                        <SelectValue placeholder="Choisir un profil…" />
                                    </SelectTrigger>
                                    <SelectContent className="max-h-72">
                                        {(options.data?.quality_profiles ?? []).map((p) => (
                                            <SelectItem key={p.id} value={String(p.id)}>
                                                {p.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            )}
                        </div>

                        {/* Film : disponibilité minimale — Série : type */}
                        <div className="space-y-1.5">
                            <Label htmlFor={ids.extra}>{isMovie ? "Disponibilité minimale" : "Type de série"}</Label>
                            {isMovie ? (
                                <Select value={availability} onValueChange={setAvailability}>
                                    <SelectTrigger id={ids.extra}>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {MOVIE_AVAILABILITY.map((o) => (
                                            <SelectItem key={o.value} value={o.value}>
                                                {o.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            ) : (
                                <Select value={seriesType} onValueChange={setSeriesType}>
                                    <SelectTrigger id={ids.extra}>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {SERIES_TYPES.map((o) => (
                                            <SelectItem key={o.value} value={o.value}>
                                                {o.label}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            )}
                            <p className="text-[11px] text-muted-foreground">
                                {isMovie
                                    ? "À partir de quand Radarr considère le film comme disponible au téléchargement."
                                    : "« Anime » active la numérotation absolue, « Quotidienne » les émissions datées."}
                            </p>
                        </div>

                        {/* Tags */}
                        <fieldset className="space-y-2">
                            <legend className="text-sm font-medium leading-none">Tags</legend>
                            {options.isLoading ? (
                                <div className="flex gap-1.5 pt-1">
                                    <Shimmer className="h-6 w-16 rounded-full" />
                                    <Shimmer className="h-6 w-20 rounded-full" />
                                    <Shimmer className="h-6 w-14 rounded-full" />
                                </div>
                            ) : (
                                <div className="flex flex-wrap gap-1.5 pt-1">
                                    {(options.data?.tags ?? []).map((t) => {
                                        const active = tags.includes(t.id);
                                        return (
                                            <button
                                                key={t.id}
                                                type="button"
                                                className="chip"
                                                data-active={active}
                                                aria-pressed={active}
                                                onClick={() => toggleTag(t.id)}
                                            >
                                                {active && <Check className="h-3 w-3" aria-hidden />}
                                                {t.label}
                                            </button>
                                        );
                                    })}
                                    {(options.data?.tags ?? []).length === 0 && (
                                        <span className="text-xs text-muted-foreground">Aucun tag existant : crée le premier ci-dessous.</span>
                                    )}
                                </div>
                            )}
                            <div className="flex items-center gap-2 pt-1">
                                <Label htmlFor={ids.tag} className="sr-only">
                                    Nouveau tag
                                </Label>
                                <Input
                                    id={ids.tag}
                                    placeholder="Nouveau tag…"
                                    value={newTag}
                                    onChange={(e) => setNewTag(e.target.value)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") {
                                            e.preventDefault();
                                            handleAddTag();
                                        }
                                    }}
                                />
                                <Button
                                    size="icon"
                                    variant="outline"
                                    aria-label="Créer le tag"
                                    disabled={!newTag.trim() || createTag.isPending}
                                    onClick={handleAddTag}
                                >
                                    {createTag.isPending ? <Loader2 className="animate-spin" /> : <Plus />}
                                </Button>
                            </div>
                        </fieldset>
                    </div>
                )}

                <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={updateMedia.isPending}>
                        Annuler
                    </Button>
                    <Button onClick={handleSave} disabled={updateMedia.isPending || options.isLoading || options.isError}>
                        {updateMedia.isPending && <Loader2 className="animate-spin" />}
                        Enregistrer
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
