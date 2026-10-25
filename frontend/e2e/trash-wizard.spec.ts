/**
 * Assistant TRaSH Guides (Maintenance › TRaSH Guides › Assistant).
 * ----------------------------------------------------------------
 * Régression constatée sur une vraie installation (Synology, Chrome
 * Windows) : les étapes 2 à 6 s'affichaient vides, et « Appliquer »
 * poussait alors des choix jamais vus. Ce test parcourt les 6 étapes et
 * vérifie qu'à chacune au moins une option est réellement VISIBLE
 * (opacité effective, en remontant tous les parents), avec et sans
 * « réduire les animations » (deux projets dans playwright.config.ts).
 */
import { expect, test, type Page } from "@playwright/test";
import { mockApi } from "./api-mock";

const RECOMMENDATION = [
    {
        profile_name: "[French MULTi.VF] UHD Bluray + WEB",
        profile_id: "e64b266178c7f70e208f493f00e0e50a",
        service_type: "radarr",
        description: "Profil TRaSH de test",
        score_profile: "french-multi-vf",
        custom_formats: [{ trash_id: "cf1", name: "MULTi", scores: null, category: "language" }],
    },
];

/** Opacité réellement perçue de l'élément (produit de celle de ses parents). */
async function effectiveOpacity(page: Page, selector: string): Promise<number[]> {
    return page.locator(selector).evaluateAll((els) =>
        els.map((el) => {
            let opacity = 1;
            for (let n: Element | null = el; n; n = n.parentElement) opacity *= parseFloat(getComputedStyle(n).opacity || "1");
            return opacity;
        }),
    );
}

async function expectOptionsVisible(page: Page, step: number) {
    const options = '[data-testid="wizard-step"] [role="radio"], [data-testid="wizard-step"] [role="switch"]';
    await expect(page.locator(options).first(), `étape ${step} : aucune option`).toBeVisible();
    // Laisse l'animation d'entrée se terminer, puis exige une opacité pleine
    await expect
        .poll(async () => Math.min(...(await effectiveOpacity(page, options))), { message: `étape ${step} : options invisibles`, timeout: 3_000 })
        .toBeGreaterThan(0.99);
}

test.beforeEach(async ({ page }) => {
    await mockApi(page, [
        [/^\/api\/trash-guides\/status$/, () => ({ last_sync: null, sonarr_cf_count: 1, radarr_cf_count: 1, sonarr_qp_count: 1, radarr_qp_count: 1, cache_age_hours: 1, is_stale: false })],
        [/^\/api\/trash-guides\/recommend$/, () => RECOMMENDATION],
    ]);
    await page.addInitScript(() => window.localStorage.removeItem("arrmada:trash-wizard-prefs"));
});

test("chaque étape affiche ses options, le résumé montre tous les choix", async ({ page }) => {
    await page.goto("/trash-guides");
    await expect(page.getByText("Quel type d'écran utilises-tu ?")).toBeVisible();

    for (let step = 1; step <= 5; step++) {
        await expectOptionsVisible(page, step);
        // On change un choix à l'étape 2 (Audio) : le résumé doit le refléter
        if (step === 2) await page.getByRole("radio", { name: /5\.1/ }).click();
        await page.getByRole("button", { name: step === 5 ? "Voir mes recommandations" : "Suivant" }).click();
    }

    // Étape 6 : résumé complet (4 questions + 2 contenus) et choix effectifs
    const summary = page.getByTestId("wizard-summary");
    await expect(summary.locator("li")).toHaveCount(6);
    await expect(summary).toContainText("5.1");
    await expect(summary).toContainText("Non");
    await expect(page.getByText("[French MULTi.VF] UHD Bluray + WEB")).toBeVisible();
    await expect(page.getByRole("button", { name: /Appliquer/ })).toBeEnabled();
});

test("« Appliquer » reste bloqué tant qu'une étape n'a pas été vue", async ({ page }) => {
    await page.goto("/trash-guides");
    await expect(page.getByText("Quel type d'écran utilises-tu ?")).toBeVisible();

    // Saut direct au résumé par la barre d'étapes : Audio, Langue… jamais vues
    await page.locator('button[aria-current="step"]').locator("xpath=../button[last()]").click();
    await expect(page.getByRole("status")).toContainText("Audio");
    await expect(page.getByRole("button", { name: /Appliquer/ })).toBeDisabled();

    // Une fois chaque étape vue, le bouton se débloque
    for (const [i, title] of ["Audio", "Langue", "Qualité", "Contenu"].entries()) {
        await page.locator("button", { hasText: title }).first().click();
        await expectOptionsVisible(page, i + 2);
    }
    await page.locator("button", { hasText: "Résumé" }).first().click();
    await expect(page.getByRole("button", { name: /Appliquer/ })).toBeEnabled();
});
