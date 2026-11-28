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

// Fiche film minimale (format de GET /api/media/movie/{id})
const MOVIE = {
    id: 20, type: "movie", title: "Inception", original_title: "Inception", year: 2010, overview: "Un voleur de rêves.",
    genres: ["Science-fiction"], runtime: 148, status: "released", monitored: true, has_file: true, size_on_disk: 0,
    added: null, path: "/movies/Inception (2010)", certification: "", tmdb_id: 27205, imdb_id: "tt1375666",
    ratings: {}, images: { poster: null, fanart: null, banner: null },
}; // prettier-ignore

test("fiche film : ma note Trakt, puis noter pour un autre profil", async ({ page }) => {
    const rated: { rating: number; profile_key: number; tmdb_id: number }[] = [];
    await mockApi(page, [
        [/^\/api\/media\/movie\/20$/, () => MOVIE],
        [/^\/api\/kodi\/watch-summary$/, () => ({ movies: {}, series: {} })],
        [
            /^\/api\/trakt\/accounts$/,
            () => ({ configured: true, profiles: [profile(1, "Famille", true, false), profile(2, "Jeff", false, true), profile(3, "Morgane", false, true)] }),
        ],
        // Jeff a déjà mis 4 étoiles (8/10), Morgane rien
        [/^\/api\/trakt\/ratings$/, (url) => ({ linked: true, movie: url.searchParams.get("profile_key") === "2" ? 8 : null })],
    ]);
    await page.route(/\/api\/trakt\/rate$/, async (route) => {
        rated.push(route.request().postDataJSON());
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, message: "Noté 3,5 ★ sur Trakt (Bien)" }) });
    });
    await page.goto("/media/movie/20");

    const row = page.getByLabel("Ma note Trakt");
    await expect(row.getByText("4 ★ · Très bien")).toBeVisible(); // Jeff, premier profil relié
    await row.getByRole("radio", { name: "Morgane" }).click();
    await expect(row.getByText("Pas encore notée")).toBeVisible();

    await row.getByRole("button", { name: "Noter 3,5 étoiles" }).click();
    await expect(page.getByText("Noté 3,5 ★ sur Trakt (Bien)")).toBeVisible();
    expect(rated).toEqual([expect.objectContaining({ kind: "movie", rating: 7, tmdb_id: 27205, profile_key: 3 })]);
});
