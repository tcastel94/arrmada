/**
 * Version de l'interface ArrMada.
 * ----------------------------------------------------------------
 * Avant : « v0.1.0 » écrit en dur dans la page Paramètres (jamais à jour).
 * Ordre de priorité :
 *  1. NEXT_PUBLIC_APP_VERSION (injectable au build Docker, ex: tag git) ;
 *  2. le champ `version` du package.json du frontend.
 * Webpack n'embarque que la propriété lue (tree-shaking JSON), pas tout
 * le package.json.
 */
import pkg from "../../../package.json";

export const APP_VERSION: string = process.env.NEXT_PUBLIC_APP_VERSION || pkg.version;
