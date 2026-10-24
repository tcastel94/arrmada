/**
 * Assistant d'installation (premier lancement).
 * ----------------------------------------------------------------
 * Ces routes /api/setup/* sont PUBLIQUES côté backend (pas encore de mot
 * de passe à ce stade) : on utilise donc `fetch` directement et non
 * `apiFetch`, qui redirigerait vers /login sur un 401.
 * Tous les messages d'erreur sont traduits ici (le backend répond en
 * anglais) pour que l'assistant reste 100 % en français.
 */
import { useQuery } from "@tanstack/react-query";
import { API_URL } from "@/lib/constants";

export interface SetupStatus {
    is_configured: boolean;
    /** Faux tant qu'aucun mot de passe admin n'a été créé (instance « libre »). */
    password_set: boolean;
    has_services: boolean;
    services_count: number;
    database_type: string;
}

export interface DiscoveredService {
    type: string;
    name: string;
    url: string;
    port: number;
    host: string;
    version: string | null;
    needs_api_key: boolean;
    status: string;
}

export interface ServiceSetupItem {
    name: string;
    type: string;
    url: string;
    api_key: string;
    is_enabled: boolean;
}

/** Message FR quand le backend est injoignable (réseau, conteneur arrêté…). */
const UNREACHABLE = "Impossible de joindre le backend ArrMada. Vérifie que le conteneur arrmada tourne.";

export function useSetupStatus() {
    return useQuery<SetupStatus>({
        queryKey: ["setup-status"],
        queryFn: async () => {
            const res = await fetch(`${API_URL}/api/setup/status`).catch(() => {
                throw new Error(UNREACHABLE);
            });
            if (res.status === 502) throw new Error("Le backend ArrMada démarre ou est arrêté. Patiente quelques secondes puis réessaie.");
            if (!res.ok) throw new Error(`Le backend a répondu une erreur (HTTP ${res.status}).`);
            return res.json();
        },
        retry: 1,
        staleTime: 30_000,
    });
}

/**
 * Scan réseau des services *arr.
 * Sans argument : le backend scanne les adresses courantes du sous-réseau.
 * Avec `hosts` : ne sonde que ces machines (utilisé par « Tester »).
 * Correctif : on n'envoie plus `JSON.stringify(null)` (corps "null") ; sans
 * hôtes précis, la requête part sans corps.
 */
export async function discoverServices(hosts?: string[]): Promise<DiscoveredService[]> {
    const init: RequestInit = { method: "POST" };
    if (hosts && hosts.length > 0) {
        init.headers = { "Content-Type": "application/json" };
        init.body = JSON.stringify(hosts);
    }
    const res = await fetch(`${API_URL}/api/setup/discover`, init).catch(() => {
        throw new Error(UNREACHABLE);
    });
    if (!res.ok) throw new Error("La détection réseau a échoué côté serveur.");
    return res.json();
}

/** Résultat du test d'une ligne de l'assistant. */
export interface SetupTestResult {
    ok: boolean;
    /** Message court affiché sous la ligne. */
    label: string;
    version?: string | null;
}

/**
 * Teste une ligne de l'assistant AVANT l'installation.
 * Il n'existe pas encore de route publique pour valider une clé API ; on
 * réutilise donc la découverte ciblée sur l'hôte de l'URL : le backend
 * vérifie qu'il JOINT bien le service (c'est lui qui s'y connectera, pas le
 * navigateur). Limite : seuls les ports par défaut sont sondés, et la clé
 * API n'est vérifiée qu'au premier contrôle de santé.
 */
export async function testSetupService(item: Pick<ServiceSetupItem, "type" | "url">): Promise<SetupTestResult> {
    let parsed: URL;
    try {
        parsed = new URL(item.url.trim());
    } catch {
        return { ok: false, label: "URL invalide : elle doit ressembler à http://192.168.1.10:8989" };
    }
    const host = parsed.hostname;
    const port = parsed.port ? Number(parsed.port) : parsed.protocol === "https:" ? 443 : 80;
    const found = await discoverServices([host]);
    const sameType = found.filter((f) => f.type === item.type);
    const match = sameType.find((f) => f.port === port);
    if (match) {
        return {
            ok: true,
            version: match.version,
            label: match.version
                ? `Joignable depuis ArrMada · v${match.version}`
                : "Joignable depuis ArrMada (la clé API sera vérifiée au premier contrôle)",
        };
    }
    if (sameType.length > 0) {
        return {
            ok: false,
            label: `Service trouvé sur ${host}, mais sur le port ${sameType[0].port} (pas ${port}).`,
        };
    }
    return {
        ok: false,
        label: `Rien trouvé sur ${host}:${port}. Vérifie l'adresse, le port et que le conteneur tourne.`,
    };
}

/** Transforme les erreurs FastAPI (texte anglais ou liste de validation) en FR. */
function setupErrorMessage(status: number, body: unknown): string {
    if (status === 409) {
        return "ArrMada est déjà configuré : connecte-toi, puis ajoute tes services dans Paramètres → Services *arr.";
    }
    if (status === 400) return "Ajoute au moins un service complet pour terminer.";
    if (status === 428) return "Crée d'abord le mot de passe administrateur (étape Sécurité).";
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (status === 422 && Array.isArray(detail)) {
        // ex: loc = ["body","services",0,"url"] → « service n°1 : champ url »
        const first = detail[0] as { loc?: (string | number)[] } | undefined;
        const loc = first?.loc ?? [];
        const idx = loc.find((p) => typeof p === "number");
        const field = loc[loc.length - 1];
        const fieldFr: Record<string, string> = { name: "nom", url: "URL", api_key: "clé API", type: "type" };
        const label = typeof field === "string" ? fieldFr[field] ?? field : "champ";
        return typeof idx === "number"
            ? `Service n°${idx + 1} : ${label} invalide ou manquant.`
            : `Données invalides (${label}).`;
    }
    return `La configuration a échoué (HTTP ${status}).`;
}

export async function completeSetup(services: ServiceSetupItem[]) {
    const res = await fetch(`${API_URL}/api/setup/complete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ services }),
    }).catch(() => {
        throw new Error(UNREACHABLE);
    });
    if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(setupErrorMessage(res.status, err));
    }
    return res.json() as Promise<{ success: boolean; services_added: number; message: string }>;
}
