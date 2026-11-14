/**
 * Assistant IA : une demande, des cartes d'action, Valider / Annuler.
 * Réponses reprises du format de /api/ai (tests backend test_ai_actions.py).
 */
import { expect, test } from "@playwright/test";
import { mockApi } from "./api-mock";

test("demande en clair, carte d'action validée, carte non résolue", async ({ page }) => {
    const decided: string[] = [];
    await mockApi(page, [[/^\/api\/ai\/settings$/, () => ({ mode: "confirm", configured: true })]]);
    await page.route(/\/api\/ai\/act$/, (route) =>
        route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({
                reply: "Je l'ajoute et je complète la saga.",
                engine: "ollama",
                mode: "confirm",
                proposals: [
                    { id: "p1", type: "request_movie", summary: "Ajouter le film Interstellar (2014) à Radarr et le chercher", status: "pending", message: "" },
                    { id: "p2", type: "complete_saga", summary: "Compléter la saga « Matrix »", status: "unresolved", message: "Aucune saga « Matrix » dans Radarr" },
                ],
            }),
        }),
    );
    await page.route(/\/api\/ai\/act\/p1\/(confirm|cancel)$/, (route) => {
        decided.push(new URL(route.request().url()).pathname);
        return route.fulfill({
            status: 200,
            contentType: "application/json",
            body: JSON.stringify({ id: "p1", type: "request_movie", summary: "Ajouter le film Interstellar (2014) à Radarr et le chercher", status: "done", message: "Interstellar ajouté, recherche lancée" }),
        });
    });

    await page.goto("/assistant");
    await page.getByLabel("Demande à l'assistant").fill("ajoute interstellar et complète matrix");
    await page.getByRole("button", { name: "Demander" }).click();
    await expect(page.getByText("Je l'ajoute et je complète la saga.")).toBeVisible();
    await expect(page.getByText("Aucune saga « Matrix » dans Radarr")).toBeVisible();
    // Une seule carte attend une décision
    await expect(page.getByRole("button", { name: "Valider" })).toHaveCount(1);
    await page.getByRole("button", { name: "Valider" }).click();
    await expect(page.getByText("Interstellar ajouté, recherche lancée")).toBeVisible();
    expect(decided).toEqual(["/api/ai/act/p1/confirm"]);
});
