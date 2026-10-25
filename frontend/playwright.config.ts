/**
 * Tests de bout en bout (navigateur réel) de l'interface.
 * ----------------------------------------------------------------
 * Pourquoi un vrai navigateur : certains défauts ne se voient qu'au rendu
 * (une animation qui ne se joue pas laisse un contenu à opacité 0). Un test
 * de composant en mémoire (jsdom) ne calcule ni styles ni animations.
 *
 * L'API est entièrement simulée dans le navigateur (page.route) : aucun
 * backend à lancer, le test ne dépend que de l'interface construite.
 *
 *   npm run build && npm run test:e2e
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.E2E_PORT || 3999);

export default defineConfig({
    testDir: "./e2e",
    fullyParallel: true,
    retries: process.env.CI ? 1 : 0,
    reporter: process.env.CI ? [["list"], ["github"]] : "list",
    use: {
        baseURL: `http://127.0.0.1:${PORT}`,
        locale: "fr-FR",
        trace: "retain-on-failure",
    },
    projects: [
        { name: "chromium", use: { ...devices["Desktop Chrome"] } },
        // Même parcours avec « réduire les animations » demandé par l'OS
        { name: "chromium-reduced-motion", use: { ...devices["Desktop Chrome"], contextOptions: { reducedMotion: "reduce" } } },
    ],
    webServer: {
        // Interface déjà construite (`npm run build`) : le rendu de production
        command: `npx next start -p ${PORT}`,
        url: `http://127.0.0.1:${PORT}/login`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
});
