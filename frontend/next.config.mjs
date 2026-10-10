/** @type {import('next').NextConfig} */
const nextConfig = {
    output: "standalone",
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
