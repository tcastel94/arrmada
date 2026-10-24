import type { MetadataRoute } from "next";

/**
 * Manifeste d'application web (PWA).
 * ----------------------------------------------------------------
 * Permet « Ajouter à l'écran d'accueil » sur Android / Chrome : l'app
 * s'ouvre alors en plein écran, sans barre d'adresse, avec son icône,
 * comme une app installée. (iPhone : réglages équivalents dans
 * `appleWebApp` de app/layout.tsx.)
 */
export default function manifest(): MetadataRoute.Manifest {
    return {
        name: "ArrMada",
        short_name: "ArrMada",
        description: "Ta médiathèque, tes téléchargements et ton salon, au même endroit",
        start_url: "/dashboard",
        display: "standalone",
        background_color: "#000000",
        theme_color: "#000000",
        lang: "fr",
        icons: [
            { src: "/logo-mark-192.png", sizes: "192x192", type: "image/png" },
            { src: "/logo-mark.png", sizes: "512x512", type: "image/png", purpose: "any" },
        ],
    };
}
