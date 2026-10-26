/**
 * Dossiers vidéo : refus avec la ligne de volume à ajouter.
 * ----------------------------------------------------------------
 * Retour d'installation réelle (Synology) : « /volume1/mangas » était refusé
 * par « Dossier refusé : il doit être sous /mnt/user », sans dire qu'il
 * fallait d'abord monter le dossier dans le conteneur. Parcours vérifié :
 * saisie du chemin du NAS → la ligne de volume s'affiche (copiable) avec le
 * chemin à saisir → « Utiliser ce chemin » remplit le champ → ajout accepté.
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

// Réponse réelle de POST /api/videos/roots (tests backend test_videos.py)
const REFUSAL = {
    detail: {
        message:
            "Dossier refusé : il doit être sous /mnt/user ou /data, tel que le voit le conteneur ArrMada. /volume1/mangas est " +
            "sans doute un chemin du NAS : monte-le dans le service arrmada du docker-compose.yml, relance le conteneur, " +
            "puis saisis /mnt/user/mangas.",
        volume_line: "- /volume1/mangas:/mnt/user/mangas:ro",
        container_path: "/mnt/user/mangas",
    },
};

test("chemin du NAS refusé : ligne de volume, puis chemin du conteneur accepté", async ({ page }) => {
    const posted: string[] = [];
    let roots: { id: number; name: string; path: string; available: boolean }[] = [];
    await mockApi(page, [
        // GET : liste + bases ; le POST est traité plus bas (il lit le corps envoyé)
        [/^\/api\/videos\/roots$/, () => ({ items: roots, bases: ["/mnt/user", "/data"] })],
    ]);
    // POST : on lit le chemin envoyé pour répondre comme le serveur
    await page.route(/\/api\/videos\/roots$/, async (route) => {
        if (route.request().method() !== "POST") return route.fallback();
        const body = route.request().postDataJSON() as { name: string; path: string };
        posted.push(body.path);
        if (body.path.startsWith("/volume1")) {
            return route.fulfill({ status: 422, contentType: "application/json", body: JSON.stringify(REFUSAL) });
        }
        roots = [{ id: 1, name: body.name, path: body.path, available: true }];
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(roots[0]) });
    });

    await page.goto("/settings/dossiers");
    await expect(page.getByText("Aucun dossier pour l'instant")).toBeVisible();
    await page.getByRole("button", { name: "Ajouter" }).first().click();

    const dialog = page.getByRole("dialog");
    // L'aide reprend les bases du serveur
    await expect(dialog.getByText("sous /mnt/user ou /data")).toBeVisible();
    await dialog.getByLabel("Nom affiché sur la TV").fill("Mangas");
    await dialog.getByLabel("Chemin sur le serveur").fill("/volume1/mangas");
    await dialog.getByRole("button", { name: "Ajouter" }).click();

    const hint = dialog.getByTestId("mount-hint");
    await expect(hint).toBeVisible();
    await expect(hint).toContainText("chemin du NAS");
    await expect(hint.getByTestId("volume-line")).toHaveText("- /volume1/mangas:/mnt/user/mangas:ro");
    await expect(hint.getByRole("button", { name: "Copier" })).toBeVisible();

    await hint.getByRole("button", { name: "Utiliser ce chemin" }).click();
    await expect(dialog.getByLabel("Chemin sur le serveur")).toHaveValue("/mnt/user/mangas");
    await dialog.getByRole("button", { name: "Ajouter" }).click();

    await expect(page.getByText("Dossier « Mangas » ajouté")).toBeVisible();
    expect(posted).toEqual(["/volume1/mangas", "/mnt/user/mangas"]);
});
