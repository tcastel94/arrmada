/**
 * Identifiant de CE build de l'interface (nouvelle valeur à chaque
 * `next build`, donc à chaque image Docker). Il est inscrit dans le code
 * envoyé au navigateur ET servi par /build-id : une page restée ouverte des
 * jours (tablette en kiosque) compare les deux et se recharge toute seule
 * après une mise à jour, comme un service qu'on redémarre après un
 * changement de binaire. ARRMADA_BUILD_ID permet de le fixer (CI).
 */
const BUILD_ID = process.env.ARRMADA_BUILD_ID || Date.now().toString(36);

/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
    env: {
        NEXT_PUBLIC_ARRMADA_BUILD: BUILD_ID,
    },
    eslint: {
        // Lint errors don't block production builds
        // (linting runs separately in CI via `npm run lint`)
        ignoreDuringBuilds: true,
    },
    typescript: {
        // Type errors don't block production builds
        // (type-checking runs separately in CI via `tsc --noEmit`)
        ignoreBuildErrors: true,
    },
    /**
     * Réorganisation des menus (v2) : les anciennes URLs restent valides
     * (favoris, liens Telegram…) et pointent vers leur nouvel emplacement.
     * `permanent: false` → redirection 307, non mise en cache par le
     * navigateur, donc réversible facilement.
     */
    /**
     * Développement uniquement (`npm run dev`) : relaie /api vers le backend
     * lancé à part (uvicorn :8000), pour que le front appelle l'API en
     * relatif comme en production. En production c'est docker/gateway.js
     * qui fait ce travail (le proxy intégré de Next coupe les flux SSE au
     * bout de 30 s, les compresse et masque l'IP du client).
     */
    async rewrites() {
        if (process.env.NODE_ENV === "production") return [];
        const backend = process.env.ARRMADA_DEV_API_URL || "http://127.0.0.1:8000";
        return [
            { source: "/api/:path*", destination: `${backend}/api/:path*` },
            { source: "/kodi/:path*", destination: `${backend}/kodi/:path*` },
        ];
    },
    async redirects() {
        return [
            { source: "/quality", destination: "/health?tab=quality", permanent: false },
            { source: "/duplicates", destination: "/health?tab=duplicates", permanent: false },
            { source: "/cleanup", destination: "/health?tab=cleanup", permanent: false },
            { source: "/fichiers", destination: "/downloads?tab=imports", permanent: false },
            { source: "/docker", destination: "/system?tab=docker", permanent: false },
            { source: "/requests", destination: "/search?tab=tracking", permanent: false },
            { source: "/recommendations", destination: "/search?tab=discover", permanent: false },
            { source: "/services", destination: "/settings/services", permanent: false },
            { source: "/settings/profile-overrides", destination: "/trash-guides?tab=overrides", permanent: false },
            { source: "/settings/sabnzbd-config", destination: "/trash-guides?tab=sabnzbd", permanent: false },
        ];
    },
};

export default nextConfig;
