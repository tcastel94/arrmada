/**
 * Paramètres › Trakt (ADR-022) : un compte par profil, liaison par code.
 * ----------------------------------------------------------------
 * Réponses reprises de l'API (tests backend test_trakt.py) : la page affiche
 * le code à taper sur trakt.tv/activate, interroge /link/poll (en attente,
 * puis relié) et le profil passe en « @compte ».
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

const SETTINGS = {
    telegram: { configured: false, bot_token_set: false, chat_id_set: false },
    tmdb: { configured: true },
    auth: { jwt_expiration_hours: 24, default_secret: false, password_source: "file" },
    cors: { origins: [] },
    scheduler: { health_check_interval: "60s" },
    version: "e2e",
};

const profile = (id: number, name: string, isDefault: boolean, linked: boolean) => ({
    id, name, color: "#4A9EFF", emoji: "", is_default: isDefault, profile_key: isDefault ? 0 : id,
    linked, username: linked ? "jeff_trakt" : "", linked_at: linked ? "2026-11-28T08:00:00+00:00" : null,
}); // prettier-ignore

test("relier le compte Trakt d'un profil avec le code d'activation", async ({ page }) => {
    let jeffLinked = false;
    let polls = 0;
    await mockApi(page, [
        [/^\/api\/settings$/, () => SETTINGS],
        [/^\/api\/ai\/settings$/, () => ({ mode: "confirm", configured: true, telegram: { configured: false, alerts: true } })],
        [
            /^\/api\/trakt\/accounts$/,
            () => ({ configured: true, profiles: [profile(1, "Famille", true, false), profile(2, "Jeff", false, jeffLinked)] }),
        ],
        [
            /^\/api\/trakt\/link$/,
            () => ({ device_code: "dev-code-123456", user_code: "ABCD1234", verification_url: "https://trakt.tv/activate", expires_in: 600, interval: 1 }),
        ],
        [
            /^\/api\/trakt\/link\/poll$/,
            () => {
                polls += 1;
                if (polls < 2) return { status: "pending" };
                jeffLinked = true;
                return { status: "linked", username: "jeff_trakt" };
            },
        ],
    ]);
    await page.goto("/settings");

    // La ligne du profil (le toast « Trakt relié … pour Jeff » est aussi un élément de liste)
    const jeff = page.getByRole("listitem").filter({ has: page.getByText("Jeff", { exact: true }) });
    await expect(jeff.getByText("Pas de compte Trakt")).toBeVisible();
    await jeff.getByRole("button", { name: "Relier" }).click();

    // Code à taper sur trakt.tv/activate, attente affichée
    await expect(page.getByLabel("Code Trakt")).toHaveText("ABCD1234");
    await expect(page.getByRole("link", { name: /trakt\.tv\/activate/ })).toHaveAttribute("href", "https://trakt.tv/activate");
    await expect(page.getByText("En attente de la validation sur Trakt…")).toBeVisible();

    // Tapé sur Trakt : le profil passe en « relié »
    await expect(jeff.getByText("@jeff_trakt")).toBeVisible({ timeout: 10_000 });
    await expect(jeff.getByRole("button", { name: "Délier" })).toBeVisible();
    await expect(page.getByLabel("Code Trakt")).toHaveCount(0);
});

test("Trakt non configuré : la marche à suivre", async ({ page }) => {
    await mockApi(page, [
        [/^\/api\/settings$/, () => SETTINGS],
        [/^\/api\/trakt\/accounts$/, () => ({ configured: false, profiles: [] })],
    ]);
    await page.goto("/settings");
    await expect(page.getByText("TRAKT_CLIENT_ID=…")).toBeVisible();
    await expect(page.getByRole("link", { name: "trakt.tv (My Apps)" })).toBeVisible();
});
