"use client";

import { useEffect, useState } from "react";

/**
 * Retarde la propagation d'une valeur (ex: texte tapé dans une recherche)
 * pour n'interroger l'API qu'une fois la frappe terminée — au lieu d'une
 * requête par touche.
 */
export function useDebounce<T>(value: T, delay = 300): T {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const t = setTimeout(() => setDebounced(value), delay);
        return () => clearTimeout(t);
    }, [value, delay]);
    return debounced;
}
