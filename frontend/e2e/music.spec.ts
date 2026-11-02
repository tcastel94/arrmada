/**
 * Musique (Lidarr) : grille des artistes, ajout d'un artiste, fiche.
 * ----------------------------------------------------------------
 * Réponses reprises du format de /api/music (tests backend test_music.py).
 * Parcours vérifié : la grille s'affiche, le conseil Jellyfin aussi tant que
 * la bibliothèque « Musique » manque ; la recherche propose « Suivre » et
 * envoie l'identifiant MusicBrainz ; la fiche range albums et singles.
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

const RADIOHEAD = {
    id: 2,
    mbid: "a74b1b7f-71a5-4011-9441-d0b5e4122711",
    name: "Radiohead",
    overview: "Groupe anglais.",
    genres: ["Alternative", "Rock"],
    poster: null,
    fanart: null,
    albums: 3,
    tracks_have: 20,
    tracks_total: 30,
    size_bytes: 900_000_000,
    monitored: true,
};

const STATUS = {
    lidarr: true,
    jellyfin: true,
    jellyfin_libraries: [],
    ready: false,
    hint: "Dans Jellyfin, ajoute une bibliothèque de type « Musique » qui pointe sur le dossier musique de Lidarr pour pouvoir écouter.",
};

test("artistes, conseil Jellyfin et ajout d'un artiste", async ({ page }) => {
    const followed: string[] = [];
    await mockApi(page, [
        [/^\/api\/music\/status$/, () => STATUS],
        [/^\/api\/music\/artists$/, () => ({ artists: [RADIOHEAD], total: 1 })],
        [/^\/api\/music\/queue$/, () => ({ items: [] })],
        [
            /^\/api\/music\/lookup$/,
            () => ({
                results: [
                    { mbid: "056e4f3e-d505-4dad-8ec1-d04f521cbb56", name: "Daft Punk", overview: null, type: "Group", genres: ["Electronic"], poster: null, in_library: false },
                    { mbid: RADIOHEAD.mbid, name: "Radiohead", overview: null, type: "Group", genres: [], poster: null, in_library: true },
                ],
            }),
        ],
    ]);
    // POST : on relève l'artiste suivi
    await page.route(/\/api\/music\/artists$/, async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        const body = route.request().postDataJSON() as { mbid: string };
        followed.push(body.mbid);
        return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ ...RADIOHEAD, id: 9, name: "Daft Punk" }) });
    });

    await page.goto("/music");
    await expect(page.getByRole("heading", { name: "Musique", level: 1 })).toBeVisible();
    await expect(page.getByText(/bibliothèque de type « Musique »/)).toBeVisible();
    await expect(page.getByText("Radiohead").first()).toBeVisible();
    await expect(page.getByText("3 albums · 20/30 pistes")).toBeVisible();

    await page.getByPlaceholder("Nom d'un artiste ou d'un groupe").fill("daft");
    await expect(page.getByText("Daft Punk")).toBeVisible();
    // Déjà suivi : pas de bouton, la mention « Suivi »
    await expect(page.getByRole("button", { name: "Suivre" })).toHaveCount(1);
    await page.getByRole("button", { name: "Suivre" }).click();
    await expect.poll(() => followed).toEqual(["056e4f3e-d505-4dad-8ec1-d04f521cbb56"]);
});

test("fiche d'un artiste : albums puis singles, état de chaque album", async ({ page }) => {
    await mockApi(page, [
        [
            /^\/api\/music\/artists\/2$/,
            () => ({
                ...RADIOHEAD,
                album_list: [
                    { id: 11, mbid: "b1", title: "Kid A", year: 2000, type: "Album", cover: null, tracks_have: 10, tracks_total: 10, status: "complete", monitored: true },
                    { id: 12, mbid: "b2", title: "OK Computer", year: 1997, type: "Album", cover: null, tracks_have: 10, tracks_total: 12, status: "partial", monitored: true },
                    { id: 13, mbid: "b3", title: "Creep", year: 1992, type: "Single", cover: null, tracks_have: 0, tracks_total: 8, status: "missing", monitored: false },
                ],
            }),
        ],
    ]);

    await page.goto("/music/2");
    await expect(page.getByRole("heading", { name: "Radiohead", level: 1 })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Albums" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Singles" })).toBeVisible();
    await expect(page.getByText("Complet")).toBeVisible();
    await expect(page.getByText("10/12 pistes")).toBeVisible();
    await expect(page.getByText("Non suivi")).toBeVisible();
});

test("musique des téléchargements : importer un album prêt, raison affichée sinon", async ({ page }) => {
    const imported: string[] = [];
    await mockApi(page, [
        [/^\/api\/music\/status$/, () => ({ ...STATUS, jellyfin_libraries: ["Musique"], ready: true, hint: null })],
        [/^\/api\/music\/artists$/, () => ({ artists: [RADIOHEAD], total: 1 })],
        [/^\/api\/music\/queue$/, () => ({ items: [] })],
        [
            /^\/api\/music\/downloads$/,
            () => ({
                folders: ["/data/usenet/complete"],
                ignored: 2,
                albums: [
                    { folder: "/data/usenet/complete/music/Radiohead - Kid A", name: "Radiohead - Kid A", artist: "Radiohead", album: "Kid A", tracks: 10, size_bytes: 300_000_000, ready: true, reason: null },
                    { folder: "/data/usenet/complete/music/Inconnu", name: "Inconnu", artist: null, album: null, tracks: 1, size_bytes: 5_000_000, ready: false, reason: "Artiste non reconnu par Lidarr (suis-le d'abord, ou corrige les étiquettes)" },
                ],
            }),
        ],
    ]);
    await page.route(/\/api\/music\/downloads\/import$/, async (route) => {
        imported.push((route.request().postDataJSON() as { folder: string }).folder);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok", message: "Import lancé : Kid A (10 pistes)" }) });
    });

    await page.goto("/music");
    await expect(page.getByRole("heading", { name: "Dans les téléchargements" })).toBeVisible();
    await expect(page.getByText("Radiohead – Kid A")).toBeVisible();
    await expect(page.getByText(/Artiste non reconnu par Lidarr/)).toBeVisible();
    // Bonus de films écartés par le serveur : seulement mentionnés
    await expect(page.getByText(/2 bonus de films ignorés/)).toBeVisible();
    // Un seul bouton : l'album non reconnu ne s'importe pas
    await expect(page.getByRole("button", { name: "Importer" })).toHaveCount(1);
    await page.getByRole("button", { name: "Importer" }).click();
    await expect.poll(() => imported).toEqual(["/data/usenet/complete/music/Radiohead - Kid A"]);
});

test("fiche d'un artiste : recherche automatique d'un album, albums manquants, actualiser", async ({ page }) => {
    const posted: string[] = [];
    await mockApi(page, [
        [
            /^\/api\/music\/artists\/2$/,
            () => ({
                ...RADIOHEAD,
                album_list: [
                    { id: 11, mbid: "b1", title: "Kid A", year: 2000, type: "Album", cover: null, tracks_have: 10, tracks_total: 10, status: "complete", monitored: true },
                    { id: 13, mbid: "b3", title: "Creep", year: 1992, type: "Single", cover: null, tracks_have: 0, tracks_total: 8, status: "missing", monitored: false },
                ],
            }),
        ],
    ]);
    await page.route(/\/api\/music\/(albums|artists)\/\d+\/(search|refresh)$/, async (route) => {
        posted.push(new URL(route.request().url()).pathname);
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok", message: "Lancé" }) });
    });

    await page.goto("/music/2");
    // Toujours proposés, même si tout est déjà là
    await page.getByRole("button", { name: "Chercher les albums manquants" }).click();
    await page.getByRole("button", { name: "Actualiser" }).click();

    // Album complet : « meilleure version » ; album absent : « Récupérer cet album »
    await page.getByRole("button", { name: /Kid A/ }).click();
    await expect(page.getByRole("button", { name: "Chercher une meilleure version" })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: /^Creep/ }).click();
    await page.getByRole("button", { name: "Récupérer cet album" }).click();
    await expect(page.getByRole("button", { name: "Recherche lancée" })).toBeVisible();

    await expect
        .poll(() => posted)
        .toEqual(["/api/music/artists/2/search", "/api/music/artists/2/refresh", "/api/music/albums/13/search"]);
});

test("fiche d'un artiste : recherche manuelle d'un album et téléchargement d'une release", async ({ page }) => {
    const grabbed: unknown[] = [];
    await mockApi(page, [
        [
            /^\/api\/music\/artists\/2$/,
            () => ({
                ...RADIOHEAD,
                album_list: [
                    { id: 13, mbid: "b3", title: "Creep", year: 1992, type: "Single", cover: null, tracks_have: 0, tracks_total: 8, status: "missing", monitored: false },
                ],
            }),
        ],
        [
            /^\/api\/music\/albums\/13\/releases$/,
            () => ({
                total: 2,
                items: [
                    { guid: "g1", indexer_id: 2, indexer: "DrunkenSlug", title: "Radiohead-Creep-WEB-FLAC", size_bytes: 310_000_000, seeders: null, age_days: 10, quality: "FLAC", protocol: "usenet", rejected: false, rejections: [] },
                    { guid: "g2", indexer_id: 1, indexer: "NZBgeek", title: "Radiohead-Creep-MP3", size_bytes: 50_000_000, seeders: null, age_days: 3, quality: "MP3-128", protocol: "usenet", rejected: true, rejections: ["Qualité non voulue"] },
                ],
            }),
        ],
    ]);
    await page.route(/\/api\/music\/albums\/13\/grab$/, async (route) => {
        grabbed.push(route.request().postDataJSON());
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok", message: "Envoyé au téléchargement" }) });
    });

    await page.goto("/music/2");
    await page.getByRole("button", { name: /^Creep/ }).click();
    await page.getByRole("button", { name: "Recherche manuelle" }).click();
    await expect(page.getByText("Radiohead-Creep-WEB-FLAC")).toBeVisible();
    // Refusée par le profil : repliée par défaut
    await expect(page.getByText("Radiohead-Creep-MP3")).toHaveCount(0);
    await page.getByRole("button", { name: "voir les 1 refusée" }).click();
    await expect(page.getByText("Qualité non voulue")).toBeVisible();

    await page.getByRole("button", { name: "Télécharger Radiohead-Creep-WEB-FLAC" }).click();
    await expect(page.getByText("Envoyé", { exact: true })).toBeVisible();
    expect(grabbed).toEqual([{ guid: "g1", indexer_id: 2 }]);
});
