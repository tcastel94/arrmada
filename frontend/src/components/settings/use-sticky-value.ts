"use client";

/**
 * Garde la dernière valeur non nulle.
 * ----------------------------------------------------------------
 * Cas d'usage : une boîte « Modifier X » s'ouvre quand `editing` est
 * défini et se ferme quand il repasse à null. Sans ce hook, le titre et
 * le formulaire disparaîtraient AVANT la fin de l'animation de fermeture
 * (la boîte se « vide » pendant 300 ms). On continue donc d'afficher le
 * dernier élément édité le temps que la boîte se referme.
 */
import { useState } from "react";

export function useStickyValue<T>(value: T | null): T | null {
    const [sticky, setSticky] = useState<T | null>(value);
    // Mise à jour pendant le rendu : motif React officiel pour dériver un état.
    if (value !== null && value !== sticky) setSticky(value);
    return value ?? sticky;
}
