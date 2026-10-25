/**
 * GET /build-id — identifiant du build de l'interface actuellement servi.
 * ----------------------------------------------------------------
 * Lu par les pages qui restent ouvertes en permanence (écran d'appoint
 * /ecran) : si la valeur diffère de celle inscrite dans leur propre code,
 * c'est qu'ArrMada a été mis à jour depuis leur chargement → rechargement.
 * Servi par Next.js lui-même (pas par l'API) : une réponse 200 prouve aussi
 * que l'interface est prête, donc que recharger ne tombera pas sur une
 * page d'erreur pendant un redémarrage.
 */
export const dynamic = "force-dynamic";

export function GET() {
    return Response.json(
        { build: process.env.NEXT_PUBLIC_ARRMADA_BUILD ?? "" },
        // Jamais mis en cache (navigateur, Fully Kiosk, reverse proxy)
        { headers: { "Cache-Control": "no-store, max-age=0" } },
    );
}
