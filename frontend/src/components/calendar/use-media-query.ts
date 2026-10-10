"use client";

import { useEffect, useState } from "react";

/**
 * Suit une media query CSS (ex: "(max-width: 767px)").
 * Renvoie `null` tant que le navigateur n'a pas répondu (rendu serveur /
 * premier rendu) : l'appelant peut ainsi éviter d'afficher la « mauvaise »
 * vue une fraction de seconde.
 */
export function useMediaQuery(query: string): boolean | null {
    const [matches, setMatches] = useState<boolean | null>(null);
    useEffect(() => {
        const mq = window.matchMedia(query);
        const update = () => setMatches(mq.matches);
        update();
        mq.addEventListener("change", update);
        return () => mq.removeEventListener("change", update);
    }, [query]);
    return matches;
}
