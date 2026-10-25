/**
 * API ArrMada simulée dans le navigateur, juste assez pour afficher les
 * pages testées. Toute route non prévue répond une liste vide : la page
 * s'affiche, sans données.
 */
import type { Page } from "@playwright/test";

type Handler = (url: URL, method: string) => unknown;

const DEFAULTS: [RegExp, Handler][] = [
    [/^\/api\/setup\/status$/, () => ({ is_configured: true, password_set: true, has_services: true, services_count: 2, database_type: "sqlite" })],
    [/^\/api\/settings\/modules$/, () => ({ modules: {} })],
    [/^\/api\/health$/, () => ({ status: "ok", service: "arrmada", version: "e2e" })],
];

export async function mockApi(page: Page, routes: [RegExp, Handler][] = []) {
    // Session ouverte : jeton factice (l'API simulée ne le vérifie pas)
    await page.addInitScript(() => window.localStorage.setItem("arrmada_token", "e2e"));
    const table = [...routes, ...DEFAULTS];
    await page.route(/\/api\//, async (route) => {
        const url = new URL(route.request().url());
        const method = route.request().method();
        if (url.pathname.startsWith("/api/events") || url.pathname.endsWith("/stream")) {
            return route.fulfill({ status: 204, body: "" }); // flux temps réel : rien
        }
        const hit = table.find(([re]) => re.test(url.pathname));
        const body = hit ? hit[1](url, method) : [];
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });
}
