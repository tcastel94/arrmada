"use client";

/**
 * État synchronisé avec un paramètre d'URL — version « réactive ».
 * ----------------------------------------------------------------
 * Pourquoi pas `useUrlState` (hooks/use-url-state) ici : il lit l'URL dans
 * un effet APRÈS le premier rendu. Sur la médiathèque, un lien profond
 * (`/media?type=series&page=4`, retour arrière depuis une fiche…) afficherait
 * d'abord « Tout / page 1 », lancerait une requête inutile, puis basculerait.
 * Il ne voit pas non plus une navigation vers la MÊME page (la palette ⌘K
 * qui pousse `/search?q=…` alors qu'on est déjà sur /search).
 *
 * Ici on s'appuie sur `useSearchParams` de Next (valeur juste dès le premier
 * rendu, mise à jour à chaque navigation) et on écrit avec
 * `history.replaceState`, que Next ≥ 14.1 répercute sur `useSearchParams`
 * sans recharger la page ni ajouter d'entrée d'historique.
 * ⚠️ `useSearchParams` impose un <Suspense> autour du composant appelant.
 */
import { useCallback } from "react";
import { useSearchParams } from "next/navigation";

/** Met à jour plusieurs paramètres d'un coup (null / "" = suppression). */
export function writeParams(updates: Record<string, string | null | undefined>) {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") url.searchParams.delete(key);
        else url.searchParams.set(key, value);
    }
    const next = `${url.pathname}${url.search}${url.hash}`;
    const current = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    // `null` (et non window.history.state) : Next ≥ 14.1 intercepte
    // replaceState et ne synchronise son routeur (donc useSearchParams) que
    // si l'état passé n'est PAS déjà un état interne Next (`__NA`). Il recopie
    // lui-même ses données internes dans la nouvelle entrée.
    if (next !== current) window.history.replaceState(null, "", next);
}

/**
 * `[valeur, setValeur]` lié à `?key=`. `allowed` filtre les valeurs
 * inconnues (ex: `?type=foo` → valeur par défaut) pour ne jamais envoyer
 * n'importe quoi à l'API.
 */
export function useParamState<T extends string>(key: string, defaultValue: T, allowed?: readonly T[]) {
    const params = useSearchParams();
    const raw = params.get(key);
    const value: T = raw !== null && raw !== "" && (!allowed || allowed.includes(raw as T)) ? (raw as T) : defaultValue;

    const setValue = useCallback(
        (next: T) => writeParams({ [key]: next === defaultValue ? null : next }),
        [key, defaultValue],
    );

    return [value, setValue] as const;
}

/** Variante numérique (ex: `?page=3`), bornée à ≥ 1. */
export function usePageParam(key = "page") {
    const params = useSearchParams();
    const parsed = Number.parseInt(params.get(key) ?? "", 10);
    const page = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
    const setPage = useCallback((next: number) => writeParams({ [key]: next <= 1 ? null : String(next) }), [key]);
    return [page, setPage] as const;
}
