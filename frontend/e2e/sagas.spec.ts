/**
 * Sagas de films : grille avec filtres, fiche d'une saga, « Compléter ».
 * ----------------------------------------------------------------
 * Réponses reprises du format de /api/sagas (tests backend test_sagas.py).
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

const film = (tmdb: number, title: string, year: number, state: string, movie_id: number | null = null) => ({
    tmdb_id: tmdb, movie_id, title, year, overview: null, runtime: null, poster: null, state,
    watched: false, progress: null,
});

const DUNE = {
    id: 2, tmdb_id: 726871, title: "Dune", overview: "La saga d'Arrakis.", poster: null, fanart: null, posters: [],
    monitored: false, total: 3, available: 1, wanted: 0, missing: 1, upcoming: 1, complete: false, years: [2021, 2026],
    seen: 1, next: null, custom_order: false,
};
const LOTR = {
    id: 1, tmdb_id: 119, title: "Le Seigneur des anneaux", overview: null, poster: null, fanart: null, posters: [],
    monitored: false, total: 3, available: 3, wanted: 0, missing: 0, upcoming: 0, complete: true, years: [2001, 2003],
    seen: 0, next: null, custom_order: false,
};

test("grille des sagas : compteurs, badges et filtres", async ({ page }) => {
    await mockApi(page, [[/^\/api\/sagas$/, () => ({ sagas: [DUNE, LOTR], total: 2, incomplete: 1, upcoming: 1 })]]);
    await page.goto("/media/sagas");
    await expect(page.getByRole("heading", { name: "Sagas", level: 1 })).toBeVisible();
    await expect(page.getByText("2 sagas dans ta bibliothèque · 1 incomplète · 1 film annoncé")).toBeVisible();
    await expect(page.getByText("1 film manquant")).toBeVisible();
    await expect(page.getByText("Complète", { exact: true })).toBeVisible();

    await page.getByRole("button", { name: "Complètes", exact: true }).click();
    await expect(page.getByText("Le Seigneur des anneaux")).toBeVisible();
    await expect(page.getByText("Dune", { exact: true })).toHaveCount(0);
});

test("fiche d'une saga : films dans l'ordre, compléter la saga, ajouter un film", async ({ page }) => {
    const posted: unknown[] = [];
    await mockApi(page, [
        [
            /^\/api\/sagas\/2$/,
            () => ({
                ...DUNE,
                films: [
                    { ...film(438631, "Dune", 2021, "available", 20), watched: true },
                    film(693134, "Dune, deuxième partie", 2024, "missing"),
                    film(1170608, "Dune, troisième partie", 2026, "upcoming"),
                ],
            }),
        ],
    ]);
    await page.route(/\/api\/sagas\/2\/complete$/, async (route) => {
        posted.push(route.request().postDataJSON());
        return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ status: "ok", added: ["Dune, deuxième partie"], message: "1 film ajouté à Radarr, recherche lancée" }),
        });
    });

    await page.goto("/media/sagas/2");
    await expect(page.getByRole("heading", { name: "Dune", level: 1 })).toBeVisible();
    await expect(page.getByText("3 films · 2021 – 2026 · 1 sur le NAS · 1 vu")).toBeVisible();
    await expect(page.getByText("✓ Vu")).toBeVisible();
    await expect(page.getByText(/2 · 2024 · Pas sur le NAS/)).toBeVisible();
    await expect(page.getByText(/3 · 2026 · Annoncé/)).toBeVisible();
    // Le film sur le NAS mène à sa fiche
    await expect(page.locator('a[href="/media/movie/20"]')).toHaveCount(1);

    await page.getByRole("button", { name: "Compléter la saga (1 film)" }).click();
    await page.getByRole("button", { name: "Ajouter Dune, deuxième partie" }).click();
    await expect.poll(() => posted).toEqual([{}, { tmdb_ids: [693134] }]);
});

test("fiche d'une saga : suivre les nouveaux films, ordre choisi à la main", async ({ page }) => {
    const calls: { method: string; path: string; body: unknown }[] = [];
    await mockApi(page, [
        [
            /^\/api\/sagas\/2$/,
            () => ({
                ...DUNE,
                films: [
                    film(438631, "Dune", 2021, "available", 20),
                    film(693134, "Dune, deuxième partie", 2024, "available", 21),
                    film(1170608, "Dune, troisième partie", 2026, "upcoming"),
                ],
            }),
        ],
    ]);
    await page.route(/\/api\/sagas\/2\/(follow|order)$/, async (route) => {
        const req = route.request();
        calls.push({ method: req.method(), path: new URL(req.url()).pathname, body: req.postDataJSON() });
        const follow = req.url().endsWith("/follow");
        return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify(follow ? { status: "ok", monitored: true, message: "Suivie" } : { status: "ok", message: "Ordre enregistré" }),
        });
    });

    await page.goto("/media/sagas/2");
    await page.getByRole("button", { name: "Suivre les nouveaux films" }).click();
    await page.getByRole("button", { name: "Ordre des films" }).click();
    // Dune, deuxième partie monte en premier
    await page.getByRole("button", { name: "Monter Dune, deuxième partie" }).click();
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect.poll(() => calls).toEqual([
        { method: "POST", path: "/api/sagas/2/follow", body: { follow: true } },
        { method: "PUT", path: "/api/sagas/2/order", body: { tmdb_ids: [693134, 438631, 1170608] } },
    ]);
});

