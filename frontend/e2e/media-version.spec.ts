/**
 * Version audio & qualité par titre : fiche d'un film, puis action groupée.
 * ----------------------------------------------------------------
 * Réponses reprises du format de /api/media-version (tests backend
 * test_media_version.py).
 */
import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./api-mock";

const FILE = {
    id: 901, relative_path: "Vaiana.2016.1080p.BluRay.x264.mkv", path: "/films/Vaiana (2016)/Vaiana.mkv", size_bytes: 9_000_000_000,
    quality: "Bluray-1080p", quality_source: "bluray", resolution: 1080, video_codec: "x264", video_dynamic_range: "",
    video_dynamic_range_type: "", audio_codec: "DTS", audio_channels: 5.1, audio_languages: "eng", subtitle_languages: "fre",
    run_time: "1:47:00", release_group: "GRP", edition: "", languages: ["English"], date_added: "2026-10-01T10:00:00Z",
};

const MOVIE = {
    id: 12, type: "movie", title: "Vaiana", original_title: "Moana", year: 2016, overview: "Une jeune navigatrice.", genres: ["Animation"],
    runtime: 107, status: "released", monitored: true, quality_profile_id: 4, minimum_availability: "released", has_file: true,
    size_on_disk: 9_000_000_000, added: "2026-10-01T10:00:00Z", path: "/films/Vaiana (2016)", certification: "", tmdb_id: 277834,
    ratings: {}, images: { poster: null, fanart: null, banner: null }, file: FILE, cast: [], crew: [], subtitles: [], tags: [],
};

const choice = (language: string, quality: string, dub = "any", installed = false) => ({
    language, quality, dub, installed, profile_name: installed ? "profil" : null,
});

const CHOICES = ["1080p", "2160p"].flatMap((q) => [
    choice("vf", q), choice("vf", q, "france"), choice("vf", q, "quebec"), choice("multi", q, "any", true), choice("vostfr", q), choice("vo", q),
]);

const state = (version: unknown, matches: boolean | null, reason: string | null = null) => ({
    media_type: "movie", id: 12, title: "Vaiana", monitored: true, original_language: "English",
    profile: { id: 4, name: version ? "[French MULTi.VF] HD Bluray + WEB · VFF" : "HD-1080p" },
    version, quality_guess: "1080p", choices: CHOICES,
    file: {
        has_file: true, files_total: 1, files_matching: matches ? 1 : 0, files_mismatching: matches === false ? 1 : 0,
        audio_languages: ["English"], tags: [], matches, reason,
    },
});

/** Fiche du film + version ; `puts` reçoit ce que l'interface envoie. */
async function mockMovie(page: Page, puts: unknown[]) {
    let current: unknown = null;
    await mockApi(page, [
        [/^\/api\/media\/movie\/12$/, () => MOVIE],
        [/^\/api\/media-version\/movie\/12$/, () => state(current, current ? false : null, current ? "Pas de piste audio française" : null)],
        [/^\/api\/kodi\/watch-summary$/, () => ({ movies: {}, series: {} })],
    ]);
    await page.route(/\/api\/media-version\/movie\/12$/, async (route) => {
        if (route.request().method() !== "PUT") return route.fallback();
        const body = route.request().postDataJSON();
        puts.push(body);
        current = { language: body.language, quality: body.quality, dub: body.dub };
        return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                status: "ok", version: current, changed: true, action: body.action, file_deleted: body.action === "replace", monitored: true, warnings: [],
                profile: { id: 101, name: "[French MULTi.VF] HD Bluray + WEB · VFF", created: true },
            }),
        });
    });
}

test("fiche d'un film : choisir la VF France et chercher une meilleure release", async ({ page }) => {
    const puts: unknown[] = [];
    await mockMovie(page, puts);
    await page.goto("/media/movie/12");

    // Le bouton est visible dans la barre d'actions, sans passer par un menu
    await page.getByRole("button", { name: "Version", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Version de « Vaiana »")).toBeVisible();
    await expect(dialog.getByText("profil « HD-1080p »")).toBeVisible();
    await expect(dialog.getByText("Anglais")).toBeVisible();

    await dialog.getByRole("radio", { name: /^VF Piste française/ }).click();
    await dialog.getByRole("radio", { name: "France (VFF)" }).click();
    await expect(dialog.getByRole("radio", { name: "1080p" })).toBeChecked();
    // Film déjà téléchargé : trois issues possibles, « chercher » par défaut
    await expect(dialog.getByRole("radio", { name: /Chercher une meilleure release/ })).toBeChecked();
    await expect(dialog.getByRole("radio", { name: /Remplacer maintenant/ })).toBeVisible();
    await dialog.getByRole("button", { name: "Enregistrer et chercher" }).click();

    await expect.poll(() => puts).toEqual([{ language: "vf", quality: "1080p", dub: "france", action: "search" }]);
    await expect(page.getByText("Vaiana : VF (VFF) · 1080p")).toBeVisible();
    // Le bouton affiche maintenant la version voulue
    await expect(page.getByRole("button", { name: /VF \(VFF\) · 1080p/ })).toBeVisible();
});

test("fiche d'un film : remplacer le fichier demande un bouton explicite", async ({ page }) => {
    const puts: unknown[] = [];
    await mockMovie(page, puts);
    await page.goto("/media/movie/12?tab=files");

    // Panneau « Version & qualité » de l'onglet Fichiers
    await expect(page.getByRole("heading", { name: "Version & qualité" })).toBeVisible();
    await page.getByRole("button", { name: "Choisir une version…" }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("radio", { name: /^VF Piste française/ }).click();
    await dialog.getByRole("radio", { name: "4K" }).click();
    await dialog.getByRole("radio", { name: /Remplacer maintenant/ }).click();
    await dialog.getByRole("button", { name: "Supprimer et retélécharger" }).click();

    await expect.poll(() => puts).toEqual([{ language: "vf", quality: "2160p", dub: "any", action: "replace" }]);
    await expect(page.getByText("Fichier supprimé, recherche lancée.")).toBeVisible();
    // Le panneau signale que le fichier présent n'est pas (encore) le bon
    await expect(page.getByRole("tabpanel").getByText("Ne correspond pas : pas de piste audio française")).toBeVisible();
});

test("médiathèque : même version pour une sélection", async ({ page }) => {
    const item = (id: number, title: string, type = "movie") => ({
        external_id: String(id), tmdb_id: id, title, type, year: 2020, genres: ["Animation"], quality: "Bluray-1080p", size_bytes: 1,
        poster_url: null, source_service: type === "movie" ? "radarr" : "sonarr", has_file: true, monitored: true, status: "released",
        added: "2026-10-01T10:00:00Z", rating: null, runtime: 90, overview: "",
    });
    const posted: unknown[] = [];
    await mockApi(page, [
        [/^\/api\/media\/sources$/, () => ({ degraded: false, sources: [] })],
        [/^\/api\/artwork\/status$/, () => ({ running: false, sources: { fanart: true, tmdb: true, local: true }, stored: { titles: 0, images: 0 } })],
        [/^\/api\/media$/, () => ({ items: [item(1, "Vaiana"), item(2, "Encanto"), item(7, "Bluey", "series")], pagination: { page: 1, per_page: 50, total: 3, total_pages: 1 } })],
        [/^\/api\/kodi\/watch-summary$/, () => ({ movies: {}, series: {} })],
    ]);
    await page.route(/\/api\/media-version\/bulk$/, async (route) => {
        posted.push(route.request().postDataJSON());
        return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ status: "ok", total: 3, changed: 3, searched: 0, created_profiles: ["x"], warnings: [] }),
        });
    });
    await page.goto("/media");
    await expect(page.getByText("Vaiana").first()).toBeVisible();

    await page.getByRole("button", { name: /Sélectionner/ }).first().click();
    await page.getByRole("button", { name: /Tout sélectionner|Page/ }).click();
    await page.getByRole("toolbar").getByRole("button", { name: "Version" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByText("Version de 2 films et 1 série")).toBeVisible();
    await dialog.getByRole("radio", { name: /^VF Piste française/ }).click();
    await dialog.getByRole("button", { name: "Appliquer à 3 titres" }).click();

    await expect.poll(() => posted).toEqual([
        {
            items: [{ type: "movie", id: 1 }, { type: "movie", id: 2 }, { type: "series", id: 7 }],
            language: "vf", quality: null, dub: "france", action: "none",
        },
    ]);
    await expect(page.getByText("Version VF (VFF)")).toBeVisible();
});
