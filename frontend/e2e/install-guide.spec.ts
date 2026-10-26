/**
 * Guide d'installation web (docs/installation/index.html, GitHub Pages).
 * ----------------------------------------------------------------
 * Retour d'installation réelle (Synology) : le dossier partagé « data »
 * avait été créé à la main (invisible en SMB, donc pour Kodi), la corbeille
 * gardait les fichiers remplacés, les applis « injoignables » par l'IP du NAS
 * (hairpin), et rien n'indiquait les sources à ajouter dans Kodi. Vérifié :
 * ces points apparaissent dans le parcours Synology, avec l'adresse saisie.
 * Page statique : ouverte directement (file://), sans serveur.
 */
import path from "node:path";
import { pathToFileURL } from "node:url";
import { expect, test } from "@playwright/test";

const GUIDE = pathToFileURL(path.resolve(__dirname, "../../docs/installation/index.html")).href;

test("parcours Synology : dossier data, réseau des applis, sources Kodi", async ({ page }) => {
    await page.goto(GUIDE);
    await page.getByRole("radio", { name: /NAS Synology/ }).click();
    await page.locator("#next-device").click();
    await page.locator("#next-choices").click();

    const steps = page.locator("#steps");
    await expect(steps).toContainText("Activer la Corbeille");
    await steps.getByText("Mon dossier « data » existe déjà").click();
    await expect(steps.getByRole("link", { name: "documentation de l'installeur" })).toHaveAttribute(
        "href",
        /docs\/installer\.md#synology-dsm-72$/,
    );

    await page.locator("#next-install").click();
    await page.locator("#host").fill("192.168.1.49");
    const first = page.locator("#first-steps");
    await expect(first).toContainText("Une application en rouge ?");
    await expect(first).toContainText("Utiliser http://radarr:7878");
    // L'adresse saisie est reprise dans les sources Kodi, sans recharger
    await expect(first).toContainText("smb://192.168.1.49/data/media/movies");
    await expect(first).toContainText("smb://192.168.1.49/data/media/tv");
});

test("serveur Linux : pas d'étapes propres au NAS", async ({ page }) => {
    await page.goto(GUIDE);
    await page.getByRole("radio", { name: /Linux/ }).click();
    await page.locator("#next-device").click();
    await page.locator("#next-choices").click();
    await page.locator("#next-install").click();
    const first = page.locator("#first-steps");
    await expect(first).toContainText("Ouvre ArrMada");
    await expect(first).not.toContainText("smb://");
    await expect(first).not.toContainText("Une application en rouge ?");
});
