"use client";

/**
 * Rechargement automatique d'une page ouverte en permanence (tablette en
 * kiosque sur /ecran).
 * ----------------------------------------------------------------
 * Une page web chargée une fois garde son code tant qu'on ne la recharge
 * pas : après une mise à jour d'ArrMada, la tablette continuerait de faire
 * tourner l'ANCIENNE version (et ses anciennes adresses), parfois des
 * semaines. Deux garde-fous, comme une sonde de supervision qui relance un
 * service :
 *
 *  1. Nouvelle version : toutes les 5 min, on lit /build-id. S'il diffère
 *     de l'identifiant inscrit dans le code de la page → rechargement.
 *  2. Panne qui dure : si la page n'arrive plus à joindre l'API depuis
 *     3 min alors que l'interface, elle, répond → rechargement (au plus une
 *     fois toutes les 30 min, pour ne pas boucler si le souci est ailleurs).
 *
 * On ne recharge JAMAIS si /build-id ne répond pas : pendant un
 * redémarrage du conteneur, la tablette garderait sinon une page d'erreur.
 * L'URL reçoit `v=<build>` : contourne un cache trop zélé (Fully Kiosk).
 */
import { useEffect, useRef } from "react";

const OWN_BUILD = process.env.NEXT_PUBLIC_ARRMADA_BUILD ?? "";
const CHECK_MS = 5 * 60_000;
const FAILING_RELOAD_MS = 3 * 60_000;
const FAILING_RELOAD_MIN_GAP_MS = 30 * 60_000;
const LAST_RELOAD_KEY = "arrmada_self_reload_at";

/** Build servi actuellement, ou null si l'interface ne répond pas. */
async function servedBuild(): Promise<string | null> {
    try {
        const res = await fetch(`/build-id?t=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) return null;
        const body = (await res.json()) as { build?: string };
        return typeof body.build === "string" ? body.build : null;
    } catch {
        return null;
    }
}

function reloadTo(build: string) {
    const url = new URL(window.location.href);
    url.searchParams.set("v", build || String(Date.now()));
    window.location.replace(url.toString());
}

function lastReloadAt(): number {
    try {
        return Number(sessionStorage.getItem(LAST_RELOAD_KEY) || 0);
    } catch {
        return 0;
    }
}

function markReload() {
    try {
        sessionStorage.setItem(LAST_RELOAD_KEY, String(Date.now()));
    } catch {
        /* stockage indisponible : la limite de 30 min ne s'applique pas */
    }
}

/**
 * @param lastOkAt   horodatage (ms) du dernier appel réussi à l'API, 0 si
 *                   aucun encore (dataUpdatedAt de React Query)
 * @param watchdog   faux quand la panne n'est pas réparable par un
 *                   rechargement (jeton révoqué 401, accès refusé 403)
 *
 * Pourquoi « dernier succès » plutôt que « en erreur » : React Query efface
 * l'erreur à chaque nouvel essai, l'état « en panne » clignote donc toutes
 * les 10 s. L'âge du dernier succès, lui, ne fait que grandir pendant une
 * vraie panne.
 */
export function useSelfUpdate(lastOkAt: number, watchdog: boolean) {
    // 1. Nouvelle version servie
    useEffect(() => {
        if (!OWN_BUILD) return;
        const check = async () => {
            const build = await servedBuild();
            if (build && build !== OWN_BUILD) reloadTo(build);
        };
        const timer = window.setInterval(check, CHECK_MS);
        return () => window.clearInterval(timer);
    }, []);

    // 2. Panne qui dure : aucun succès depuis 3 min (ou depuis l'ouverture)
    const mountedAt = useRef(Date.now());
    const lastOk = useRef(lastOkAt);
    lastOk.current = lastOkAt;
    useEffect(() => {
        if (!watchdog) return;
        const timer = window.setInterval(async () => {
            const since = lastOk.current || mountedAt.current;
            if (Date.now() - since < FAILING_RELOAD_MS) return;
            if (Date.now() - lastReloadAt() < FAILING_RELOAD_MIN_GAP_MS) return;
            const build = await servedBuild();
            if (build === null) return; // interface injoignable : on attend
            markReload();
            reloadTo(build);
        }, 30_000);
        return () => window.clearInterval(timer);
    }, [watchdog]);
}
