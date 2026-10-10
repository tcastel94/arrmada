"use client";

/**
 * Ajout d'un titre à Radarr/Sonarr — logique partagée par tous les onglets
 * de « Rechercher & Ajouter » (résultats, suggestions, aperçu, ajout manuel).
 * ----------------------------------------------------------------
 * Un seul fournisseur (contexte React) garde l'état « en cours / ajouté » de
 * chaque titre : ajouter un film depuis les Suggestions l'affiche aussi
 * comme ajouté dans les résultats de recherche.
 *
 * Identifiants — source du bug « mauvaise série ajoutée » :
 *  - tmdb_id = TOUJOURS un vrai ID TMDB (films, séries TMDB) ;
 *  - tvdb_id = ID TVDB (séries trouvées via Sonarr).
 * Le backend résout TMDB → TVDB pour les séries qui n'ont qu'un ID TMDB.
 */
import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { useCreateRequest } from "@/hooks/use-requests";
import type { LookupItem } from "@/hooks/use-search";
import type { TMDBItem } from "@/hooks/use-recommendations";

/** Titre ajoutable, quelle que soit sa provenance (lookup *arr ou TMDB). */
export interface AddableItem {
    /** Clé stable (dédoublonnage + état d'ajout). */
    key: string;
    title: string;
    type: "movie" | "series";
    year: number | null;
    overview: string;
    poster_url: string | null;
    /** Note TMDB /10 (suggestions uniquement). */
    rating: number | null;
    tmdb_id: number | null;
    tvdb_id: number | null;
    in_library: boolean;
}

export type AddState = "idle" | "adding" | "added";

function makeKey(type: string, tmdb: number | null, tvdb: number | null, title: string, year: number | null) {
    if (tmdb) return `${type}:tmdb:${tmdb}`;
    if (tvdb) return `${type}:tvdb:${tvdb}`;
    return `${type}:title:${title.toLowerCase()}:${year ?? ""}`;
}

/** Résultat du lookup Radarr/Sonarr → AddableItem. */
export function fromLookup(it: LookupItem): AddableItem {
    // Compatibilité : un backend plus ancien renvoyait l'ID TVDB d'une série
    // dans `tmdb_id` (et pas de champ `tvdb_id`).
    const legacySeries = it.type === "series" && it.tvdb_id === undefined;
    const tmdb = legacySeries ? null : it.tmdb_id || null;
    const tvdb = legacySeries ? it.tmdb_id || null : it.tvdb_id ?? null;
    return {
        key: makeKey(it.type, tmdb, tvdb, it.title, it.year),
        title: it.title,
        type: it.type,
        year: it.year ?? null,
        overview: it.overview ?? "",
        poster_url: it.poster_url,
        rating: null,
        tmdb_id: tmdb,
        tvdb_id: tvdb,
        in_library: it.in_library,
    };
}

/** Suggestion TMDB (tendances, « parce que tu as… ») → AddableItem. */
export function fromTmdb(it: TMDBItem): AddableItem {
    const type = it.type === "series" ? "series" : "movie";
    const year = it.year ? Number.parseInt(String(it.year), 10) || null : null;
    return {
        key: makeKey(type, it.tmdb_id, null, it.title, year),
        title: it.title,
        type,
        year,
        overview: it.overview ?? "",
        poster_url: it.poster_url ?? null,
        rating: typeof it.rating === "number" && it.rating > 0 ? it.rating : null,
        tmdb_id: it.tmdb_id,
        tvdb_id: null,
        in_library: !!it.in_library,
    };
}

/** Lien vers la fiche externe (TMDB en priorité, sinon TheTVDB). */
export function externalLink(it: Pick<AddableItem, "type" | "tmdb_id" | "tvdb_id">): { href: string; label: string } | null {
    if (it.tmdb_id) {
        return {
            href: `https://www.themoviedb.org/${it.type === "series" ? "tv" : "movie"}/${it.tmdb_id}`,
            label: "TMDB",
        };
    }
    if (it.type === "series" && it.tvdb_id) {
        return { href: `https://thetvdb.com/dereferrer/series/${it.tvdb_id}`, label: "TheTVDB" };
    }
    return null;
}

interface AdderApi {
    /** Ajoute le titre ; renvoie true si Radarr/Sonarr l'a accepté. */
    add: (item: AddableItem) => Promise<boolean>;
    stateOf: (key: string) => AddState;
}

const AdderContext = createContext<AdderApi | null>(null);

export function AdderProvider({ children, onShowTracking }: { children: ReactNode; onShowTracking?: () => void }) {
    const { mutateAsync } = useCreateRequest();
    const [states, setStates] = useState<Record<string, AddState>>({});
    // Verrou synchrone : empêche un double-clic d'envoyer deux demandes.
    const inFlight = useRef(new Set<string>());

    const add = useCallback(
        async (item: AddableItem) => {
            const setState = (key: string, state: AddState) => setStates((prev) => ({ ...prev, [key]: state }));
            if (inFlight.current.has(item.key)) return false;
            inFlight.current.add(item.key);
            setState(item.key, "adding");
            const service = item.type === "movie" ? "Radarr" : "Sonarr";
            const trackingAction = onShowTracking ? { label: "Voir le suivi", onClick: onShowTracking } : undefined;
            try {
                const res = await mutateAsync({
                    title: item.title,
                    type: item.type,
                    tmdb_id: item.tmdb_id,
                    tvdb_id: item.tvdb_id,
                    year: item.year,
                    poster_url: item.poster_url,
                });
                // Le backend renvoie 201 même quand l'ajout a échoué côté *arr :
                // avant, l'interface annonçait « ajouté » dans tous les cas.
                if (res?.status === "failed") {
                    setState(item.key, "idle");
                    toast.error(`${service} n'a pas pu ajouter « ${item.title} »`, {
                        description: "Titre introuvable ou service injoignable. Essaie l'ajout manuel avec l'ID exact.",
                        action: trackingAction,
                    });
                    return false;
                }
                setState(item.key, "added");
                if (res?.status === "available") {
                    toast.success(`« ${item.title} » est déjà dans ta bibliothèque`, { action: trackingAction });
                } else {
                    toast.success(`« ${item.title} » ajouté à ${service}`, {
                        description: "Recherche lancée sur tes indexers.",
                        action: trackingAction,
                    });
                }
                return true;
            } catch (e) {
                setState(item.key, "idle");
                toast.error(`Échec de l'ajout de « ${item.title} »`, {
                    description: e instanceof Error ? e.message : undefined,
                });
                return false;
            } finally {
                inFlight.current.delete(item.key);
            }
        },
        [mutateAsync, onShowTracking],
    );

    const stateOf = useCallback((key: string): AddState => states[key] ?? "idle", [states]);
    const value = useMemo(() => ({ add, stateOf }), [add, stateOf]);

    return <AdderContext.Provider value={value}>{children}</AdderContext.Provider>;
}

export function useAdder(): AdderApi {
    const ctx = useContext(AdderContext);
    if (!ctx) throw new Error("useAdder doit être utilisé à l'intérieur de <AdderProvider>");
    return ctx;
}
