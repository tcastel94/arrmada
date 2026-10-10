"use client";

/**
 * Champ de recherche « debouncé » ET synchronisé à l'URL (?q=…).
 * ----------------------------------------------------------------
 * - `input`  : ce que l'utilisateur tape (mis à jour à chaque touche) ;
 * - `search` : la même valeur, mais seulement 300 ms après la dernière
 *   frappe → c'est elle qu'on envoie à l'API (une requête par recherche,
 *   pas une par touche) et qu'on écrit dans l'URL.
 * Au chargement, la valeur présente dans l'URL pré-remplit le champ (lien
 * partagé / favori). L'URL n'est réécrite qu'après une vraie saisie, pour
 * ne pas effacer ?q= avant même de l'avoir lu.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useDebounce } from "@/hooks/use-debounce";
import { useUrlState } from "@/hooks/use-url-state";

export function useUrlSearch(key = "q", delay = 300) {
    const [input, setInputState] = useState("");
    const [, setParam] = useUrlState<string>(key, "");
    const debounced = useDebounce(input, delay);
    const touched = useRef(false);

    // 1. Lecture initiale depuis l'URL.
    useEffect(() => {
        const fromUrl = new URLSearchParams(window.location.search).get(key);
        if (fromUrl) setInputState(fromUrl);
    }, [key]);

    // 2. Écriture dans l'URL (seulement après une saisie de l'utilisateur).
    useEffect(() => {
        if (touched.current) setParam(debounced.trim());
    }, [debounced, setParam]);

    const setInput = useCallback((value: string) => {
        touched.current = true;
        setInputState(value);
    }, []);

    return { input, setInput, search: debounced.trim() };
}
