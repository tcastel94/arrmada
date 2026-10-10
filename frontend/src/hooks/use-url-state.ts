"use client";

/**
 * État synchronisé avec un paramètre d'URL (?tab=…, ?q=…).
 * ----------------------------------------------------------------
 * Intérêt : un onglet ou un filtre devient partageable / mis en favori, et
 * les anciennes pages redirigées (ex: /quality → /health?tab=quality)
 * ouvrent directement le bon onglet.
 * On passe par window.history (et non useSearchParams de Next) pour éviter
 * l'obligation d'un <Suspense> autour de chaque page au build.
 */
import { useCallback, useEffect, useState } from "react";

export function useUrlState<T extends string>(key: string, defaultValue: T) {
    const [value, setValue] = useState<T>(defaultValue);

    // Lecture initiale depuis l'URL (côté navigateur uniquement).
    useEffect(() => {
        const fromUrl = new URLSearchParams(window.location.search).get(key);
        if (fromUrl !== null) setValue(fromUrl as T);
    }, [key]);

    const update = useCallback(
        (next: T) => {
            setValue(next);
            const url = new URL(window.location.href);
            if (next === defaultValue || next === "") url.searchParams.delete(key);
            else url.searchParams.set(key, next);
            window.history.replaceState(window.history.state, "", url.toString());
        },
        [key, defaultValue],
    );

    return [value, update] as const;
}
