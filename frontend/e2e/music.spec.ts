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
