"use client";

/**
 * Création d'un override de profil TRaSH.
 * ----------------------------------------------------------------
 * Avant : il fallait taper à la main l'ID numérique Sonarr/Radarr et le
 * titre. Maintenant on CHERCHE le média dans la bibliothèque (recherche
 * ArrMada) : titre, type, ID et service sont déduits du résultat choisi.
 * Le service n'est plus figé au premier rendu (il suit le média choisi
 * et la liste des services une fois chargée). Option « Appliquer tout de
 * suite » pour que Sonarr/Radarr basculent immédiatement.
 */
import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Search, Target, X } from "lucide-react";
import { toast } from "sonner";
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
import { PosterThumb } from "@/components/health/media-row";
import { useMediaSearch, type MediaItem } from "@/hooks/use-media";
import { useServices } from "@/hooks/use-services";
import { useDebounce } from "@/hooks/use-debounce";
import {
    useApplyOverride,
    useAvailableProfiles,
    useCreateOverride,
    type ProfileOverride,
} from "@/hooks/use-profile-overrides";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { notifyApplyResult } from "./notify";

export function AddOverrideDialog({
    open,
    onOpenChange,
    existing,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    existing: ProfileOverride[];
}) {
    const { data: services } = useServices();
    const create = useCreateOverride();
    const apply = useApplyOverride();

    const [query, setQuery] = useState("");
    const debounced = useDebounce(query.trim(), 300);
    const search = useMediaSearch(debounced);
    const [media, setMedia] = useState<MediaItem | null>(null);
    const [serviceId, setServiceId] = useState<string>("");
    const [profile, setProfile] = useState("");
    const [note, setNote] = useState("");
    const [applyNow, setApplyNow] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const serviceType = media?.type === "series" ? "sonarr" : "radarr";
    const candidates = useMemo(
        () => (services ?? []).filter((s) => s.type.toLowerCase() === serviceType && s.is_enabled),
        [services, serviceType],
    );
    const profiles = useAvailableProfiles(media ? serviceType : "");

    // Service par défaut = celui qui héberge le média choisi (sinon le 1er
    // du bon type). Recalculé quand le média ou la liste des services change.
    useEffect(() => {
        if (!media) return;
        const owner = candidates.find((s) => s.name === media.source_service) ?? candidates[0];
        setServiceId(owner ? String(owner.id) : "");
        setProfile("");
    }, [media, candidates]);

    const reset = () => {
        setQuery("");
        setMedia(null);
        setServiceId("");
        setProfile("");
        setNote("");
        setApplyNow(true);
    };

    const handleOpenChange = (next: boolean) => {
        if (submitting) return;
        if (!next) reset();
        onOpenChange(next);
    };

    const externalId = media ? Number(media.external_id) : NaN;
    const replaces = media && existing.find((o) => o.service_id === Number(serviceId) && o.external_id === externalId);
    const canSubmit = !!media && Number.isFinite(externalId) && !!serviceId && !!profile && !submitting;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!canSubmit || !media) return;
        setSubmitting(true);
        try {
            const created = await create.mutateAsync({
                media_type: media.type,
                external_id: externalId,
                title: media.title,
                profile_name: profile,
                service_id: Number(serviceId),
                note: note.trim() || undefined,
            });
            const profileName = profiles.data?.find((p) => p.filename === profile)?.display_name ?? profile;
            if (applyNow) {
                try {
                    const res = await apply.mutateAsync(created.id);
                    notifyApplyResult(media.title, profileName, res);
                } catch (err) {
                    toast.warning("Override enregistré, mais application impossible", {
                        description: err instanceof Error ? err.message : undefined,
                    });
                }
            } else {
                toast.success(`Override enregistré pour « ${media.title} »`, {
                    description: "Pense à l'appliquer pour que Sonarr/Radarr changent de profil.",
                });
            }
            setSubmitting(false);
            reset();
            onOpenChange(false);
        } catch (err) {
            setSubmitting(false);
            toast.error("Impossible d'enregistrer l'override", { description: err instanceof Error ? err.message : undefined });
        }
    };

    const results = search.data?.items.slice(0, 8) ?? [];

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Target className="h-5 w-5 text-orange-300" />
                        Forcer un profil pour un média
                    </DialogTitle>
                    <DialogDescription>Choisis un film ou une série de ta bibliothèque, puis le profil TRaSH à lui appliquer.</DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    {/* 1. Média */}
                    <div className="space-y-2">
                        <Label>Média</Label>
                        <AnimatePresence mode="wait" initial={false}>
                            {media ? (
                                <motion.div
                                    key="selected"
                                    initial={{ opacity: 0, scale: 0.97 }}
                                    animate={{ opacity: 1, scale: 1 }}
                                    exit={{ opacity: 0, scale: 0.97 }}
                                    transition={{ duration: 0.2, ease: EASE_OUT }}
                                    className="flex items-center gap-3 rounded-2xl bg-orange-500/10 p-2.5 ring-1 ring-orange-400/30"
                                >
                                    <PosterThumb src={media.poster_url} alt={media.title} type={media.type} />
                                    <div className="min-w-0 flex-1">
                                        <p className="truncate text-sm font-semibold">{media.title}</p>
                                        <p className="text-xs text-muted-foreground">
                                            {[media.year ?? "·", media.type === "series" ? "Série" : "Film", media.source_service].join(" · ")}
                                        </p>
                                    </div>
                                    <Button type="button" variant="ghost" size="icon-sm" aria-label="Changer de média" onClick={() => setMedia(null)}>
                                        <X />
                                    </Button>
                                </motion.div>
                            ) : (
                                <motion.div key="search" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="space-y-2">
                                    <div className="relative">
                                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                                        <Input
                                            autoFocus
                                            value={query}
                                            onChange={(e) => setQuery(e.target.value)}
                                            placeholder="Titre d'un film ou d'une série…"
                                            className="pl-9"
                                            aria-label="Rechercher un média"
                                        />
                                        {search.isFetching && (
                                            <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
                                        )}
                                    </div>
                                    {debounced.length >= 2 && (
                                        <div className="max-h-64 overflow-y-auto rounded-2xl bg-white/[0.02] p-1 ring-1 ring-white/[0.06]">
                                            {search.isError ? (
                                                <p className="p-3 text-xs text-destructive">Recherche impossible : {search.error.message}</p>
                                            ) : results.length === 0 && !search.isFetching ? (
                                                <p className="p-3 text-xs text-muted-foreground">Aucun média trouvé pour « {debounced} ».</p>
                                            ) : (
                                                <ul>
                                                    {results.map((m) => (
                                                        <li key={`${m.source_service}:${m.type}:${m.external_id}`}>
                                                            <button
                                                                type="button"
                                                                onClick={() => setMedia(m)}
                                                                className="flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors hover:bg-white/[0.05] focus-visible:bg-white/[0.05] focus-visible:outline-none"
                                                            >
                                                                <PosterThumb src={m.poster_url} alt={m.title} type={m.type} className="h-12 w-8" />
                                                                <span className="min-w-0 flex-1">
                                                                    <span className="block truncate text-sm font-medium">{m.title}</span>
                                                                    <span className="block text-xs text-muted-foreground">
                                                                        {[m.year ?? "·", m.type === "series" ? "Série" : "Film", m.source_service].join(" · ")}
                                                                    </span>
                                                                </span>
                                                            </button>
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    )}
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>

                    {/* 2. Service + profil */}
                    <div className={cn("grid gap-4 sm:grid-cols-2 transition-opacity", !media && "pointer-events-none opacity-40")}>
                        <div className="space-y-2">
                            <Label htmlFor="override-service">Service</Label>
                            <Select value={serviceId} onValueChange={setServiceId} disabled={!media}>
                                <SelectTrigger id="override-service">
                                    <SelectValue placeholder={candidates.length ? "Choisir…" : "Aucun service"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {candidates.map((s) => (
                                        <SelectItem key={s.id} value={String(s.id)}>
                                            {s.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="override-profile">Profil TRaSH</Label>
                            <Select value={profile} onValueChange={setProfile} disabled={!media || profiles.isLoading}>
                                <SelectTrigger id="override-profile">
                                    <SelectValue placeholder={profiles.isLoading ? "Chargement…" : "Choisir un profil…"} />
                                </SelectTrigger>
                                <SelectContent>
                                    {(profiles.data ?? []).map((p) => (
                                        <SelectItem key={p.filename} value={p.filename}>
                                            {p.display_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {profiles.isError && <p className="text-xs text-destructive">Profils indisponibles : synchronise TRaSH.</p>}
                        </div>
                    </div>

                    <div className={cn("space-y-2 transition-opacity", !media && "pointer-events-none opacity-40")}>
                        <Label htmlFor="override-note">Note (facultatif)</Label>
                        <Input
                            id="override-note"
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                            placeholder="Ex : anime → 1080p seulement"
                            disabled={!media}
                        />
                    </div>

                    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-xl bg-white/[0.03] p-3 ring-1 ring-white/[0.06]">
                        <span className="text-sm">
                            Appliquer tout de suite
                            <span className="block text-xs text-muted-foreground">Bascule le média sur ce profil dans Sonarr/Radarr.</span>
                        </span>
                        <Switch checked={applyNow} onCheckedChange={setApplyNow} aria-label="Appliquer tout de suite" />
                    </label>

                    {replaces && (
                        <p className="rounded-xl bg-warning/10 px-3 py-2 text-xs text-warning ring-1 ring-warning/20">
                            Ce média a déjà un override : il sera remplacé.
                        </p>
                    )}

                    <DialogFooter>
                        <Button type="button" variant="ghost" onClick={() => handleOpenChange(false)} disabled={submitting}>
                            Annuler
                        </Button>
                        <Button type="submit" disabled={!canSubmit}>
                            {submitting && <Loader2 className="animate-spin" />}
                            {applyNow ? "Enregistrer et appliquer" : "Enregistrer"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
