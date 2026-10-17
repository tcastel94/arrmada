import type { Metadata, Viewport } from "next";

/**
 * Écran d'appoint (tablette sous la TV) : page plein écran, HORS de la
 * coquille de l'appli (pas de menu, pas de connexion admin). Elle a son
 * propre accès : un jeton « écran » en lecture seule, obtenu par appairage.
 */
export const metadata: Metadata = {
    title: "Écran du salon",
    robots: { index: false, follow: false },
};

export const viewport: Viewport = {
    themeColor: "#000000",
    colorScheme: "dark",
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
};

export default function EcranLayout({ children }: { children: React.ReactNode }) {
    return children;
}
