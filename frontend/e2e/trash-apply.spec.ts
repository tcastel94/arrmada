/**
 * « Appliquer » TRaSH : aperçu obligatoire et détaillé, puis bascule.
 * ----------------------------------------------------------------
 * Retour d'installation réelle : l'ancien aperçu n'affichait qu'un compteur
 * de formats (le profil qualité et les scores n'étaient même pas écrits).
 * Parcours vérifié : « Appliquer » grisé avant l'aperçu → l'aperçu montre
 * profil, palier d'arrêt, scores et tailles → application → proposition de
 * basculer les titres existants (compte puis confirmation).
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

const PROFILE = {
    name: "[French MULTi.VF] UHD Bluray + WEB",
    id: 9,
    action: "created",
    cutoff: "Bluray|WEB 2160p",
    min_format_score: 0,
    cutoff_format_score: 10000,
    upgrade_allowed: true,
    qualities: ["Bluray|WEB 2160p", "Remux-1080p"],
    groups: ["[HDR Formats] DV (w/o HDR fallback)"],
    scores: [
        { name: "FR Remux Tier 01", score: 1950, source: "profil" },
        { name: "DV (w/o HDR fallback)", score: -10000, source: "[HDR Formats] DV (w/o HDR fallback)" },
    ],
    unknown_qualities: [],
};

function applyResult(dryRun: boolean) {
    return {
        success: true,
        dry_run: dryRun,
        cfs_created: 79,
        cfs_updated: 0,
        cfs_unchanged: 0,
        profiles_created: 1,
        profiles_updated: 0,
        created_formats: ["FR Remux Tier 01", "DV (w/o HDR fallback)"],
        updated_formats: [],
        profiles: [PROFILE],
        sizes: [{ quality: "Bluray-2160p", min: 50.4, preferred: null, max: null }],
        warnings: [],
        errors: [],
    };
}

test("aperçu détaillé obligatoire, application puis bascule de la bibliothèque", async ({ page }) => {
    const calls: { url: string; body: Record<string, unknown> }[] = [];
    await mockApi(page, [
        [/^\/api\/trash-guides\/status$/, () => ({ last_sync: null, sonarr_cf_count: 1, radarr_cf_count: 1, sonarr_qp_count: 1, radarr_qp_count: 1, cache_age_hours: 1, is_stale: false })],
        [
            /^\/api\/trash-guides\/recommend$/,
            () => [
                {
                    profile_name: "french-multi-vf-uhd-bluray-web",
                    profile_id: "french-multi-vf-uhd-bluray-web",
                    service_type: "radarr",
                    description: "Profil Films",
                    score_profile: "french-multi-vf",
                    trash_name: PROFILE.name,
                    cutoff: PROFILE.cutoff,
                    qualities: PROFILE.qualities,
                    groups: PROFILE.groups,
                    custom_formats: [{ trash_id: "a", name: "DV (w/o HDR fallback)", scores: null, category: "hdr", score: -10000, source: "x" }],
                },
            ],
        ],
        [/^\/api\/services$/, () => [{ id: 1, name: "Radarr", type: "radarr", url: "http://radarr:7878", is_enabled: true, last_status: "online" }]],
    ]);
    // Écritures interceptées en dernier (priorité sur mockApi)
    await page.route(/\/api\/trash-guides\/(apply|assign-profile)$/, async (route) => {
        const body = route.request().postDataJSON() as Record<string, unknown>;
        const url = new URL(route.request().url()).pathname;
        calls.push({ url, body });
        const json = url.endsWith("apply")
            ? applyResult(Boolean(body.dry_run))
            : { profile: PROFILE.name, profile_id: 9, total: 3, to_change: 2, changed: body.dry_run ? 0 : 2, dry_run: body.dry_run };
        await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(json) });
    });

    await page.goto("/trash-guides");
    for (let i = 0; i < 4; i++) await page.getByRole("button", { name: "Suivant" }).click();
    await page.getByRole("button", { name: "Voir mes recommandations" }).click();
    await expect(page.getByText("+").first()).toBeVisible();
    await page.getByRole("button", { name: /Appliquer…/ }).click();

    const dialog = page.getByRole("dialog");
    const applyBtn = dialog.getByRole("button", { name: /^Appliquer$/ });
    await expect(applyBtn).toBeDisabled(); // aperçu d'abord

    await dialog.getByRole("button", { name: "Aperçu" }).click();
    const detail = dialog.getByTestId("apply-detail");
    await expect(detail).toContainText("rien n'a encore été modifié");
    await expect(detail).toContainText("Bluray|WEB 2160p");
    await expect(detail).toContainText("10000");
    await detail.getByRole("button", { name: /Scores des formats/ }).click();
    await expect(detail).toContainText("-10000");
    // Les réponses de l'assistant partent avec l'aperçu (groupes liés à l'écran)
    expect(calls[0].body).toMatchObject({ dry_run: true, prefs: { display_type: expect.any(String) } });

    await applyBtn.click();
    await expect(dialog.getByTestId("apply-detail")).toContainText("Appliqué");
    const switchBtn = dialog.getByRole("button", { name: /Basculer 2 titres/ });
    await expect(switchBtn).toBeVisible();
    await expect(dialog).toContainText("2 titres sur 3");
    expect(calls.filter((c) => c.url.endsWith("assign-profile")).map((c) => c.body.dry_run)).toEqual([true]);

    await switchBtn.click();
    await expect(dialog).toContainText("2 titres basculés");
    expect(calls.at(-1)).toMatchObject({ url: "/api/trash-guides/assign-profile", body: { dry_run: false, profile_name: PROFILE.name } });
});
