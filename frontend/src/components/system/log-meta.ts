/**
 * Constantes et petits utilitaires partagés par le flux de journaux
 * Docker et le diagnostic IA (onglet « Docker » de /system).
 */
import type { DockerLogEntry, DockerLogLevel, LogSeverity } from "@/hooks/use-docker";
import { parseApiDate } from "@/lib/format";

/** Couleurs par niveau : rouge = erreur, ambre = attention (cf. guide de design). */
export const LEVEL_META: Record<DockerLogLevel, { label: string; short: string; text: string; dot: string; row: string }> = {
    error: { label: "Erreur", short: "ERR", text: "text-destructive", dot: "bg-destructive", row: "bg-destructive/[0.06]" },
    warning: { label: "Avertissement", short: "WARN", text: "text-warning", dot: "bg-warning", row: "bg-warning/[0.04]" },
    info: { label: "Info", short: "INFO", text: "text-sky-100/90", dot: "bg-sky-400", row: "" },
    other: { label: "Autre", short: "", text: "text-muted-foreground", dot: "bg-white/20", row: "" },
};

/** Sévérité d'un problème détecté par l'IA. */
export const SEVERITY_META: Record<LogSeverity, { label: string; chip: string; bar: string; icon: string; rank: number }> = {
    error: { label: "Erreur", chip: "bg-destructive/15 text-destructive ring-destructive/25", bar: "from-red-500 to-rose-400", icon: "text-destructive", rank: 0 },
    warning: { label: "Avertissement", chip: "bg-warning/15 text-warning ring-warning/25", bar: "from-amber-500 to-orange-400", icon: "text-warning", rank: 1 },
    info: { label: "Info", chip: "bg-primary/15 text-primary ring-primary/25", bar: "from-sky-500 to-cyan-400", icon: "text-primary", rank: 2 },
};

/**
 * Une couleur stable par service : dans un flux où Sonarr, Radarr et
 * SABnzbd s'entremêlent, l'œil repère un service à sa couleur. Palette
 * volontairement sans rouge ni ambre (réservés aux niveaux).
 */
const SERVICE_TONES = [
    "text-primary",
    "text-primary",
    "text-teal-300",
    "text-primary",
    "text-primary",
    "text-indigo-300",
    "text-lime-300",
    "text-blue-300",
] as const;

export function serviceTone(service: string): string {
    let h = 0;
    for (let i = 0; i < service.length; i++) h = (h * 31 + service.charCodeAt(i)) | 0;
    return SERVICE_TONES[Math.abs(h) % SERVICE_TONES.length];
}

/**
 * Date d'une ligne. Docker horodate en UTC à la nanoseconde
 * (« 2026-10-10T09:12:03.123456789Z ») : on tronque aux millisecondes,
 * seul format garanti par tous les navigateurs (Safari compris).
 */
export function logDate(entry: DockerLogEntry): Date | null {
    const ts = entry.ts.replace(/(\.\d{3})\d+/, "$1");
    return parseApiDate(ts);
}

/**
 * Heure LOCALE de la ligne (le champ `time` du backend est l'heure UTC
 * brute : décalée d'1 à 2 h en France). Date ajoutée si ce n'est pas
 * aujourd'hui (un conteneur calme peut remonter des lignes de la veille).
 */
export function logClock(entry: DockerLogEntry, now = new Date()): string {
    const d = logDate(entry);
    if (!d) return entry.time;
    const clock = d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    if (d.toDateString() === now.toDateString()) return clock;
    return `${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} ${clock}`;
}

/**
 * Retrouve, parmi les services présents dans les journaux, celui que
 * l'IA a cité (elle écrit « Sonarr » là où le service s'appelle
 * « sonarr » ou « Sonarr 4K »). Renvoie null si rien ne correspond.
 */
export function matchService(name: string, available: string[]): string | null {
    const n = name.trim().toLowerCase();
    if (!n) return null;
    return (
        available.find((s) => s.toLowerCase() === n) ??
        available.find((s) => s.toLowerCase().startsWith(n) || n.startsWith(s.toLowerCase())) ??
        null
    );
}
