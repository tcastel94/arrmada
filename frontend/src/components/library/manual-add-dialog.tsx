"use client";

/**
 * Ajout manuel d'un titre (porté de l'ancienne page /requests).
 * ----------------------------------------------------------------
 * Pour les cas où la recherche ne trouve pas le bon titre : on saisit le
 * titre, le type, l'année et, idéalement, l'ID exact (TMDB pour un film ;
 * TVDB ou TMDB pour une série). Des suggestions apparaissent pendant la
 * frappe (même hook que l'onglet Rechercher, au lieu de l'ancien appel
 * réseau « fait main ») et pré-remplissent le formulaire.
 */
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Film, Loader2, Plus, Tv } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDiscoverLookup } from "@/hooks/use-search";
import { useDebounce } from "@/hooks/use-debounce";
import { cn } from "@/lib/utils";
import { EASE_OUT } from "@/lib/motion";
import { SegmentedControl } from "./segmented-control";
import { MediaThumb } from "./media-thumb";
import { fromLookup, useAdder, type AddableItem } from "./adder";

type MediaType = "movie" | "series";
type IdKind = "tmdb" | "tvdb";

export function ManualAddDialog({
    open,
    onOpenChange,
    initialTitle = "",
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Pré-remplit le titre (ex: la recherche qui n'a rien donné). */
    initialTitle?: string;
}) {
    const { add } = useAdder();
    const [title, setTitle] = useState("");
    const [type, setType] = useState<MediaType>("movie");
    const [year, setYear] = useState("");
    const [idKind, setIdKind] = useState<IdKind>("tmdb");
    const [externalId, setExternalId] = useState("");
    const [poster, setPoster] = useState<string | null>(null);
    const [picked, setPicked] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Réinitialise le formulaire à chaque ouverture.
    useEffect(() => {
        if (!open) return;
        setTitle(initialTitle);
        setType("movie");
        setYear("");
        setIdKind("tmdb");
        setExternalId("");
        setPoster(null);
        setPicked(false);
        setError(null);
    }, [open, initialTitle]);

    const debouncedTitle = useDebounce(title.trim(), 400);
    const lookup = useDiscoverLookup(debouncedTitle, open && !picked);
    const suggestions = useMemo(
        () => (lookup.data ?? []).filter((i) => i.type === type).slice(0, 5).map(fromLookup),
        [lookup.data, type],
    );

    const pick = (s: AddableItem) => {
        setTitle(s.title);
        setYear(s.year ? String(s.year) : "");
        if (s.type === "series" && s.tvdb_id) {
            setIdKind("tvdb");
            setExternalId(String(s.tvdb_id));
        } else if (s.tmdb_id) {
            setIdKind("tmdb");
            setExternalId(String(s.tmdb_id));
        } else {
            setExternalId("");
        }
        setPoster(s.poster_url);
        setPicked(true);
        setError(null);
    };

    const changeType = (next: MediaType) => {
        setType(next);
        // Un film n'a qu'un ID TMDB ; une série est par défaut identifiée par TVDB.
        setIdKind(next === "movie" ? "tmdb" : "tvdb");
        setExternalId("");
        setPoster(null);
        setPicked(false);
    };

    const submit = async (e?: FormEvent) => {
        e?.preventDefault();
        const cleanTitle = title.trim();
        if (!cleanTitle) {
            setError("Indique au moins un titre.");
            return;
        }
        const id = externalId.trim() ? Number(externalId.trim()) : null;
        if (externalId.trim() && (!Number.isInteger(id) || (id ?? 0) <= 0)) {
            setError("L'ID doit être un nombre entier (ex: 693134).");
            return;
        }
        const y = year.trim() ? Number(year.trim()) : null;
        if (year.trim() && (!Number.isInteger(y) || (y ?? 0) < 1870 || (y ?? 0) > 2100)) {
            setError("Année invalide.");
            return;
        }
        setError(null);
        const useTvdb = type === "series" && idKind === "tvdb";
        const item: AddableItem = {
            key: `manual:${type}:${useTvdb ? "tvdb" : "tmdb"}:${id ?? cleanTitle.toLowerCase()}`,
            title: cleanTitle,
            type,
            year: y,
            overview: "",
            poster_url: poster,
            rating: null,
            tmdb_id: useTvdb ? null : id,
            tvdb_id: useTvdb ? id : null,
            in_library: false,
        };
        setSubmitting(true);
        const ok = await add(item);
        setSubmitting(false);
        if (ok) onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !submitting && onOpenChange(o)}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>Ajout manuel</DialogTitle>
                    <DialogDescription>
                        Le titre est envoyé à {type === "movie" ? "Radarr" : "Sonarr"}, puis la recherche démarre. Un ID exact évite
                        toute confusion entre homonymes.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} className="space-y-4">
                    <SegmentedControl
                        layoutId="manual-type-pill"
                        ariaLabel="Type de média"
                        value={type}
                        onChange={changeType}
                        options={[
                            { value: "movie", label: "Film", icon: Film },
                            { value: "series", label: "Série", icon: Tv },
                        ]}
                    />

                    <div className="space-y-2">
                        <Label htmlFor="manual-title">Titre</Label>
                        <div className="relative">
                            <Input
                                id="manual-title"
                                autoComplete="off"
                                placeholder={type === "movie" ? "Ex : Dune : Deuxième partie" : "Ex : The Bear"}
                                value={title}
                                onChange={(e) => {
                                    setTitle(e.target.value);
                                    setPicked(false);
                                }}
                            />
                            {lookup.isFetching && !picked && (
                                <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-primary" />
                            )}
                        </div>
                        {/* Suggestions pendant la frappe */}
                        <AnimatePresence initial={false}>
                            {!picked && debouncedTitle.length >= 2 && suggestions.length > 0 && (
                                <motion.ul
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.25, ease: EASE_OUT }}
                                    className="glass max-h-64 divide-y divide-white/[0.05] overflow-y-auto rounded-xl"
                                    aria-label="Suggestions"
                                >
                                    {suggestions.map((s) => (
                                        <li key={s.key}>
                                            <button
                                                type="button"
                                                onClick={() => pick(s)}
                                                className="group flex w-full items-start gap-3 p-2.5 text-left transition-colors hover:bg-primary/[0.07]"
                                            >
                                                <MediaThumb src={s.poster_url} alt="" type={s.type} className="h-12 w-9" />
                                                <span className="min-w-0 flex-1">
                                                    <span className="flex items-center justify-between gap-2 text-sm font-medium">
                                                        <span className="truncate group-hover:text-primary">{s.title}</span>
                                                        {s.year && <span className="shrink-0 text-xs tabular-nums text-muted-foreground">{s.year}</span>}
                                                    </span>
                                                    {s.overview && <span className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{s.overview}</span>}
                                                    {s.in_library && <span className="mt-1 inline-block text-[10px] text-success">Déjà dans ta bibliothèque</span>}
                                                </span>
                                            </button>
                                        </li>
                                    ))}
                                </motion.ul>
                            )}
                        </AnimatePresence>
                        {picked && (
                            <p className="flex items-center gap-1.5 text-xs text-success">
                                <Check className="h-3.5 w-3.5" /> Formulaire pré-rempli depuis {type === "movie" ? "Radarr" : "Sonarr"}.
                            </p>
                        )}
                    </div>

                    <div className="grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)] gap-3">
                        <div className="space-y-2">
                            <div className="flex h-7 items-center">
                                <Label htmlFor="manual-year">Année</Label>
                            </div>
                            <Input
                                id="manual-year"
                                inputMode="numeric"
                                placeholder="2024"
                                value={year}
                                onChange={(e) => setYear(e.target.value.replace(/[^\d]/g, "").slice(0, 4))}
                            />
                        </div>
                        <div className="space-y-2">
                            <div className="flex h-7 items-center justify-between gap-2">
                                <Label htmlFor="manual-id">ID {idKind === "tvdb" ? "TVDB" : "TMDB"} (optionnel)</Label>
                                {type === "series" && (
                                    <SegmentedControl
                                        size="sm"
                                        layoutId="manual-id-pill"
                                        ariaLabel="Type d'identifiant"
                                        value={idKind}
                                        onChange={(v) => {
                                            setIdKind(v);
                                            setExternalId("");
                                        }}
                                        options={[
                                            { value: "tvdb", label: "TVDB" },
                                            { value: "tmdb", label: "TMDB" },
                                        ]}
                                    />
                                )}
                            </div>
                            <Input
                                id="manual-id"
                                inputMode="numeric"
                                placeholder={idKind === "tvdb" ? "79286" : "693134"}
                                value={externalId}
                                onChange={(e) => setExternalId(e.target.value.replace(/[^\d]/g, ""))}
                                className="font-mono"
                            />
                        </div>
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                        {type === "movie"
                            ? "L'ID TMDB se trouve dans l'URL de la fiche themoviedb.org (…/movie/693134)."
                            : idKind === "tvdb"
                              ? "L'ID TVDB se trouve sur la fiche thetvdb.com. Sonarr est indexé sur TVDB : c'est l'ID le plus fiable."
                              : "Avec un ID TMDB, ArrMada retrouve l'ID TVDB correspondant avant l'envoi à Sonarr."}
                    </p>

                    <AnimatePresence>
                        {error && (
                            <motion.p
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                role="alert"
                                className="animate-shake rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive ring-1 ring-destructive/25"
                            >
                                {error}
                            </motion.p>
                        )}
                    </AnimatePresence>

                    <DialogFooter>
                        <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
                            Annuler
                        </Button>
                        <Button type="submit" disabled={submitting || !title.trim()} className={cn("min-w-[8rem]")}>
                            {submitting ? <Loader2 className="animate-spin" /> : <Plus />}
                            Ajouter
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
