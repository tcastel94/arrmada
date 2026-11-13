/**
 * Copilote (/copilot) : clé d'API absente, question → outils consultés →
 * réponse en Markdown, erreur du modèle, nouvelle conversation.
 * ----------------------------------------------------------------
 * Le flux SSE de /api/copilot/chat est rejoué tel que le serveur l'émet
 * (tests backend test_copilot.py) : conversation, tool_start, tool_end,
 * text, usage, done.
 */
import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./api-mock";

const STATUS = { configured: true, model: "claude-sonnet-5-5", effort: "medium", web_search: true, documents: 19 };

const sse = (events: [string, unknown][]) => events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");

const ANSWER = sse([
    ["conversation", { id: "conv-1", restarted: false }],
    ["thinking", { delta: "", start: true }],
    ["thinking", { delta: "Je regarde les profils de Radarr." }],
    ["tool_start", { id: "t1", name: "get_quality_profiles", label: "Profils qualité", input: { service: "radarr" }, server: false }],
    ["tool_start", { id: "t2", name: "web_search", label: "Recherche web", input: { query: "trash guides remux" }, server: true }],
    ["tool_end", { id: "t1", ok: true, duration_ms: 212 }],
    ["tool_end", { id: "t2", ok: false }],
    ["text", { delta: "Ton profil **HD Bluray + WEB** est utilisé par 412 films.\n\n" }],
    ["text", { delta: "| Réglage | Actuel | TRaSH |\n|---|---|---|\n| Seuil | Bluray-1080p | Bluray-1080p |\n" }],
    ["usage", { turn: { input_tokens: 1800, output_tokens: 420, cache_read_tokens: 6200, cache_write_tokens: 0, cost_usd: 0.0084, web_searches: 1 }, model: "claude-sonnet-5-5", model_calls: 2 }],
    ["done", { ok: true, stop_reason: "end_turn" }],
]);

/** Simule /api/copilot/chat (flux SSE) et garde les corps reçus. */
async function mockChat(page: Page, body: string) {
    const posted: { message: string; conversation_id: string | null }[] = [];
    await page.route("**/api/copilot/chat", async (route) => {
        posted.push(route.request().postDataJSON());
        await route.fulfill({ status: 200, contentType: "text/event-stream", body });
    });
    return posted;
}

test("sans clé d'API : la marche à suivre, pas de zone de saisie", async ({ page }) => {
    await mockApi(page, [[/^\/api\/copilot\/status$/, () => ({ ...STATUS, configured: false })]]);
    await page.goto("/copilot");
    await expect(page.getByRole("heading", { name: "Copilote", level: 1 })).toBeVisible();
    await expect(page.getByText("Il manque une clé d'API")).toBeVisible();
    await expect(page.getByText("ANTHROPIC_API_KEY=…")).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("question → outils consultés → réponse en Markdown, puis conversation suivie", async ({ page }) => {
    await mockApi(page, [[/^\/api\/copilot\/status$/, () => STATUS]]);
    const posted = await mockChat(page, ANSWER);
    await page.goto("/copilot");

    // Écran vide : ce qui sort du réseau local est dit, des questions sont proposées
    await expect(page.getByText("Lecture seule : le copilote ne modifie aucun réglage.", { exact: false })).toBeVisible();
    const input = page.getByRole("textbox", { name: "Ta question pour le copilote" });
    await expect(page.getByRole("button", { name: "Envoyer" })).toBeDisabled();

    await input.fill("Mon profil films est-il conforme ?");
    await input.press("Enter");

    await expect(page.getByText("Mon profil films est-il conforme ?")).toBeVisible();
    // Outils : libellé, arguments résumés, durée ; un échec est signalé sans bloquer la réponse
    await expect(page.getByText("Profils qualité")).toBeVisible();
    await expect(page.getByText("radarr", { exact: true })).toBeVisible();
    await expect(page.getByText("212 ms")).toBeVisible();
    await expect(page.getByLabel("en échec")).toHaveCount(1);
    // Markdown rendu : gras et tableau, pas de syntaxe brute
    await expect(page.locator("strong", { hasText: "HD Bluray + WEB" })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "TRaSH" })).toBeVisible();
    await expect(page.getByText("**")).toHaveCount(0);
    // Consommation du tour
    // (\s : le format français met des espaces insécables dans « 0,008 $US » et « 8 000 »)
    await expect(page.getByText(/≈\s0,008\s\$US · 2 étapes · 8\s000 jetons lus · 1 recherche web · claude-sonnet-5-5/)).toBeVisible();
    // La réflexion disparaît une fois la réponse arrivée
    await expect(page.getByRole("status")).toHaveCount(0);

    // Seconde question : même conversation côté serveur
    await input.fill("Et sur Sonarr ?");
    await page.getByRole("button", { name: "Envoyer" }).click();
    await expect(page.getByText("Et sur Sonarr ?")).toBeVisible();
    expect(posted).toEqual([
        { message: "Mon profil films est-il conforme ?", conversation_id: null },
        { message: "Et sur Sonarr ?", conversation_id: "conv-1" },
    ]);

    // Nouvelle conversation : l'écran d'accueil revient, le serveur est prévenu
    const forgotten = page.waitForRequest((request) => request.method() === "DELETE" && request.url().endsWith("/api/copilot/conversations/conv-1"));
    await page.getByRole("button", { name: "Nouvelle conversation" }).click();
    await forgotten;
    await expect(page.getByText("Pour commencer")).toBeVisible();
    await expect(page.getByText("Et sur Sonarr ?")).toHaveCount(0);
});

test("une question d'amorce part d'un clic ; une erreur du modèle est affichée telle quelle", async ({ page }) => {
    await mockApi(page, [[/^\/api\/copilot\/status$/, () => STATUS]]);
    const posted = await mockChat(
        page,
        sse([
            ["conversation", { id: "conv-2", restarted: true }],
            ["error", { message: "Clé d'API Anthropic refusée : vérifie ANTHROPIC_API_KEY dans le .env, puis redémarre le conteneur." }],
            ["done", { ok: false, stop_reason: null }],
        ]),
    );
    await page.goto("/copilot");
    await page.getByRole("button", { name: /Y a-t-il des téléchargements bloqués/ }).click();

    // (Next.js a aussi un role="alert" invisible, pour annoncer les changements de page)
    await expect(page.getByRole("alert").filter({ hasText: "Clé d'API Anthropic refusée" })).toBeVisible();
    await expect(page.getByText("Le serveur a redémarré depuis ta dernière question", { exact: false })).toBeVisible();
    expect(posted[0].message).toContain("téléchargements bloqués");
    // La saisie reste utilisable pour réessayer
    await expect(page.getByRole("textbox", { name: "Ta question pour le copilote" })).toBeEnabled();
});
