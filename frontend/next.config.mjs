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
};

export default nextConfig;
