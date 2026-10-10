/**
 * Tailles « humaines » renvoyées par le backend.
 * ----------------------------------------------------------------
 * Le backend formate certaines tailles en texte (« 3,4 To », « 850,0
 * Mo » ; anciennes versions : « 1.2 TB ») sans toujours fournir le
 * nombre d'octets. Pour un affichage homogène on les reconvertit en
 * octets puis on repasse par `formatBytes` (helper unique de l'app).
 * Les deux formats (virgule + o/Ko/Mo/Go/To, ou point + B/KB/MB/GB/TB)
 * sont acceptés. Quand un champ en octets existe, l'UI l'utilise
 * directement (formatBytes) plutôt que ce texte.
 */
import { formatBytes } from "@/lib/format";

const POWERS: Record<string, number> = { B: 0, O: 0, K: 1, M: 2, G: 3, T: 4, P: 5 };

/** « 1.2 TB » / « 1,2 To » → nombre d'octets (approché). 0 si illisible. */
export function parseHumanSize(human: string | null | undefined): number {
    if (!human) return 0;
    const m = /([\d\s.,]+)\s*([KMGTP]?i?[BO])\b/i.exec(human.replace(/[  ]/g, " "));
    if (!m) return 0;
    const n = parseFloat(m[1].replace(/\s/g, "").replace(",", "."));
    if (!Number.isFinite(n)) return 0;
    const pow = POWERS[m[2][0].toUpperCase()] ?? 0;
    return n * 1024 ** pow;
}

/** Taille backend → affichage français (« 1,2 To »). */
export function frSize(human: string | null | undefined): string {
    const bytes = parseHumanSize(human);
    return bytes > 0 ? formatBytes(bytes) : "0 o";
}

/**
 * Remplace les tailles anglaises insérées dans un texte du backend
 * (« … occupent 261.3 GB ») par leur équivalent français (« 261,3 Go »).
 */
export function localizeSizes(text: string | null | undefined): string {
    if (!text) return "";
    return text.replace(/\b\d+(?:\.\d+)?\s?(?:B|KB|MB|GB|TB|PB)\b/g, (m) => frSize(m));
}
