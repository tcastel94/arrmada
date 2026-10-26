/**
 * « Tester » un service : cause de l'échec et adresse proposée.
 * ----------------------------------------------------------------
 * Retour d'installation réelle (Synology) : Radarr enregistré avec l'IP du
 * NAS, injoignable depuis le conteneur ArrMada (hairpin), alors que le nom
 * Docker « radarr » répondait. L'ancienne carte disait seulement « ne répond
 * pas ». Parcours vérifié : test en échec → la cause reste sur la carte →
 * « Utiliser http://radarr:7878 » met l'URL à jour et re-teste → succès.
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

// Message réel de diagnose_url quand le nom Docker répond (tests backend)
const DIAGNOSIS =
    "Délai dépassé sur 192.168.1.49:7878 : depuis le conteneur ArrMada, cette adresse ne répond pas " +
    "(fréquent avec l'IP du NAS sur Synology).";

test("test en échec : diagnostic sur la carte, puis bascule vers le nom Docker", async ({ page }) => {
    let url = "http://192.168.1.49:7878";
    const calls: string[] = [];
    const service = () => ({
        id: 1,
        name: "Radarr",
        type: "radarr",
        url,
        is_enabled: true,
        last_health_check: null,
        last_status: url.includes("radarr:") ? "online" : "offline",
        last_latency_ms: null,
        version: "6.4.4.10685",
        created_at: "2026-10-25T10:00:00Z",
        updated_at: "2026-10-25T10:00:00Z",
    });
    await mockApi(page, [
        [/^\/api\/services$/, () => [service()]],
        [
            /^\/api\/services\/1\/test$/,
            () => {
                calls.push(`test ${url}`);
                return url.includes("radarr:")
                    ? { success: true, status: "online", latency_ms: 4, version: "6.4.4.10685", error: null }
                    : {
                          success: false,
                          status: "offline",
                          latency_ms: null,
                          version: null,
                          error: "Connection timed out",
                          diagnosis: DIAGNOSIS,
                          suggested_url: "http://radarr:7878",
                      };
            },
        ],
        [
            /^\/api\/services\/1$/,
            (_u, method) => {
                if (method === "PUT") {
                    url = "http://radarr:7878";
                    calls.push("put");
                }
                return service();
            },
        ],
    ]);

    await page.goto("/settings/services");
    await page.getByRole("heading", { name: "Radarr" }).waitFor();
    await page.getByRole("button", { name: "Tester", exact: true }).click();

    // La cause reste affichée (pas seulement un toast qui disparaît)
    const panel = page.getByTestId("service-diagnosis");
    await expect(panel).toBeVisible();
    await expect(panel).toContainText("Délai dépassé sur 192.168.1.49:7878");
    await expect(panel).toContainText("http://radarr:7878");

    await panel.getByRole("button", { name: "Utiliser http://radarr:7878" }).click();
    await expect(page.getByText("Adresse mise à jour")).toBeVisible();
    await expect(page.getByText("Radarr répond")).toBeVisible();
    await expect(panel).toHaveCount(0);
    expect(calls).toEqual(["test http://192.168.1.49:7878", "put", "test http://radarr:7878"]);
});

test("formulaire : « Utiliser cette adresse » remplit le champ URL", async ({ page }) => {
    await mockApi(page, [
        [/^\/api\/services$/, () => []],
        [
            /^\/api\/services\/test$/,
            () => ({
                success: false,
                status: "offline",
                latency_ms: null,
                version: null,
                error: "Connection timed out",
                diagnosis: DIAGNOSIS,
                suggested_url: "http://radarr:7878",
            }),
        ],
    ]);
    await page.goto("/settings/services");
    await expect(page.getByText("Aucun service connecté")).toBeVisible();
    await page.getByRole("button", { name: "Ajouter un service" }).click();
    await page.getByRole("radio", { name: /Radarr/ }).click();
    await page.getByLabel("URL").fill("http://192.168.1.49:7878");
    await page.getByLabel(/Clé API/).fill("64efe45ba1eb4c2a9acb8740345f5f4d");
    await page.getByRole("dialog").getByRole("button", { name: "Tester", exact: true }).click();

    await expect(page.getByText(/Échec de la connexion : Délai dépassé/)).toBeVisible();
    await page.getByRole("button", { name: "Utiliser cette adresse" }).click();
    await expect(page.getByLabel("URL")).toHaveValue("http://radarr:7878");
});
