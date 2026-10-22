/**
 * Mémoire des navigations internes à l'app (pour le bouton « ‹ Retour »).
 * ----------------------------------------------------------------
 * Le bouton retour iOS doit ramener à l'écran précédent (avec ses filtres
 * et sa position de défilement), donc faire un « précédent » du navigateur.
 * Mais si on a ouvert la page directement (lien partagé, favori), un
 * « précédent » sortirait de l'app : on va alors au parent logique.
 * Ce compteur vit en mémoire le temps de l'onglet, comme une variable
 * globale de session : 1 = première page affichée, >1 = on a navigué.
 */
let depth = 0;

/** Appelé à chaque changement d'URL (layout de l'app). */
export function markNavigation(): void {
    depth += 1;
}

/** Vrai si un « précédent » reste dans l'app. */
export function canGoBack(): boolean {
    return depth > 1;
}
