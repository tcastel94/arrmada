"use client";

/**
 * Paramètres → Général.
 * ----------------------------------------------------------------
 * - Vue d'ensemble : une tuile par section (services, Kodi, Cast, Yamaha,
 *   TRaSH Guides, Salon) avec son état réel → remplace l'ancien bloc
 *   « Services connectés » qui dupliquait la page Services.
 * - Notifications Telegram (+ envoi d'un test).
 * - Configuration de l'application (lue depuis le .env du backend).
 * - À propos : versions réelles (interface + API), base de données.
 * Corrections : plus de `return null` si l'API échoue (→ ErrorState),
 * lignes colorées selon leur VRAI état (avant : toujours vertes), libellés
 * en français, version plus codée en dur.
 */
import Link from "next/link";
import { motion } from "framer-motion";
import {
    AlertTriangle,
    ArrowUpRight,
    BellRing,
    BookMarked,
    Cast,
    CheckCircle2,
    CircleDashed,
    Clock,
    Database,
    Film,
    Globe,
    Hash,
    Info,
    KeyRound,
    Loader2,
    MonitorPlay,
    Send,
    Server,
    ShieldCheck,
    Sofa,
    Speaker,
    XCircle,
    type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/shared/panel";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { RingGauge } from "@/components/fx/ring-gauge";
import { StatusDot } from "@/components/fx/status-dot";
import { APP_VERSION } from "@/components/settings/app-version";
import { useBackendVersion, useSettings, useTestTelegram } from "@/hooks/use-settings";
import { useServices } from "@/hooks/use-services";
import { useKodiSettings } from "@/hooks/use-kodi";
import { useYamahaSettings } from "@/hooks/use-yamaha";
import { useCastDevices, useJellyfinConfig } from "@/hooks/use-cast";
import { useSetupStatus } from "@/hooks/use-setup";
import { plural, percent } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { BrandIcon } from "@/components/brand/brand-mark";

/* ── Ligne de configuration ─────────────────────────────────── */

/**
 * ok = configuré et fonctionnel ; warning = optionnel mais absent ;
 * error = requis et absent ; info = simple information (gris).
 */
type RowTone = "ok" | "warning" | "error" | "info";

const ROW_TONES: Record<RowTone, { tile: string; badge: string; label: string; icon: LucideIcon }> = {
    ok: { tile: "bg-emerald-500/10 text-emerald-400", badge: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300", label: "Configuré", icon: CheckCircle2 },
    warning: { tile: "bg-amber-500/10 text-amber-400", badge: "border-amber-500/30 bg-amber-500/10 text-amber-300", label: "À configurer", icon: CircleDashed },
    error: { tile: "bg-red-500/10 text-red-400", badge: "border-red-500/30 bg-red-500/10 text-red-300", label: "Manquant", icon: XCircle },
    info: { tile: "bg-white/[0.05] text-slate-300", badge: "", label: "", icon: Info },
};

function ConfigRow({
    icon: Icon,
    label,
    value,
    tone,
    badge,
}: {
    icon: LucideIcon;
    label: string;
    value: React.ReactNode;
    tone: RowTone;
    /** Remplace le libellé de badge par défaut. */
    badge?: string;
}) {
    const t = ROW_TONES[tone];
    return (
        <div className="flex items-center gap-3 py-3">
            <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-lg", t.tile)}>
                <Icon className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{label}</p>
                <div className="truncate text-xs text-muted-foreground">{value}</div>
            </div>
            {tone !== "info" && (
                <span className={cn("hidden shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold sm:flex", t.badge)}>
                    <t.icon className="h-3 w-3" />
                    {badge ?? t.label}
                </span>
            )}
        </div>
    );
}

/* ── Tuile de la vue d'ensemble ─────────────────────────────── */

function OverviewTile({
    href,
    icon: Icon,
    iconClass,
    title,
    status,
    tone,
    gauge,
    loading,
}: {
    href: string;
    icon: LucideIcon;
    iconClass: string;
    title: string;
    status: React.ReactNode;
    /** Pastille d'état ; absente pour les simples raccourcis. */
    tone?: "online" | "warning" | "unknown" | "offline";
    gauge?: number;
    loading?: boolean;
}) {
    return (
        <motion.div variants={fadeUp}>
            <Link href={href} className="block h-full rounded-2xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                <SpotlightCard interactive className="group flex h-full items-center gap-3.5 p-4">
                    <span className={cn("relative z-[2] flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1 ring-white/[0.08]", iconClass)}>
                        <Icon className="h-5 w-5" strokeWidth={1.8} />
                    </span>
                    <div className="relative z-[2] min-w-0 flex-1">
                        <p className="flex items-center gap-1.5 text-sm font-semibold">
                            {title}
                            <ArrowUpRight className="h-3.5 w-3.5 -translate-x-1 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
                        </p>
                        {loading ? (
                            <Shimmer className="mt-1.5 h-3 w-24 rounded-md" />
                        ) : (
                            <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-muted-foreground">
                                {tone && <StatusDot tone={tone} size="sm" pulse={false} />}
                                <span className="truncate">{status}</span>
                            </p>
                        )}
                    </div>
                    {gauge !== undefined && !loading && (
                        <RingGauge value={gauge} size={44} stroke={4} tone={gauge >= 100 ? "emerald" : gauge >= 50 ? "amber" : "rose"} className="relative z-[2]">
                            <span className="text-[10px] font-semibold tabular-nums">{Math.round(gauge)}%</span>
                        </RingGauge>
                    )}
                </SpotlightCard>
            </Link>
        </motion.div>
    );
}

/* ── Page ───────────────────────────────────────────────────── */

export default function SettingsGeneralPage() {
    const { data: settings, isLoading, isError, error, refetch } = useSettings();
    const { data: backendVersion } = useBackendVersion();
    const { data: setup } = useSetupStatus();
    const services = useServices();
    const kodis = useKodiSettings();
    const amps = useYamahaSettings();
    const cast = useCastDevices();
    const jellyfin = useJellyfinConfig();
    const testTelegram = useTestTelegram();

    const enabled = services.data?.filter((s) => s.is_enabled) ?? [];
    const online = enabled.filter((s) => s.last_status === "online").length;
    const servicesGauge = enabled.length ? percent(online, enabled.length) : 0;

    const handleTestTelegram = () =>
        testTelegram.mutate(undefined, {
            onSuccess: (r) =>
                r?.success
                    ? toast.success("Notification envoyée", { description: "Jette un œil à ton chat Telegram." })
                    : toast.error("Telegram n'a pas accepté le message", {
                          description: "Vérifie le jeton du bot et l'identifiant du chat.",
                      }),
            onError: (e) => toast.error("Envoi impossible", { description: e.message }),
        });

    return (
        <motion.div variants={stagger(0, 0.06)} initial="hidden" animate="show" className="space-y-6">
            {/* ── Vue d'ensemble ─────────────────────────────── */}
            <section aria-labelledby="overview-title" className="space-y-3">
                <h2 id="overview-title" className="eyebrow">
                    Vue d&apos;ensemble
                </h2>
                <motion.div variants={stagger(0, 0.05)} className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <OverviewTile
                        href="/settings/services"
                        icon={Server}
                        iconClass="bg-primary/15 text-primary"
                        title="Services *arr"
                        loading={services.isLoading}
                        tone={enabled.length === 0 ? "unknown" : online === enabled.length ? "online" : "warning"}
                        status={
                            services.isError
                                ? "État indisponible"
                                : enabled.length === 0
                                  ? "Aucun service actif"
                                  : `${online}/${enabled.length} en ligne`
                        }
                        gauge={enabled.length ? servicesGauge : undefined}
                    />
                    <OverviewTile
                        href="/settings/kodi"
                        icon={MonitorPlay}
                        iconClass="bg-violet-500/15 text-violet-300"
                        title="Kodi"
                        loading={kodis.isLoading}
                        tone={kodis.data?.length ? "online" : "unknown"}
                        status={kodis.data?.length ? plural(kodis.data.length, "lecteur configuré", "lecteurs configurés") : "Aucun lecteur"}
                    />
                    <OverviewTile
                        href="/settings/cast"
                        icon={Cast}
                        iconClass="bg-sky-500/15 text-sky-300"
                        title="Cast & Jellyfin"
                        loading={cast.isLoading || jellyfin.isLoading}
                        tone={jellyfin.data?.configured ? "online" : "warning"}
                        status={
                            jellyfin.data?.configured
                                ? `Jellyfin prêt · ${plural(cast.data?.length ?? 0, "appareil")}`
                                : "Jellyfin à configurer"
                        }
                    />
                    <OverviewTile
                        href="/settings/yamaha"
                        icon={Speaker}
                        iconClass="bg-orange-500/15 text-orange-300"
                        title="Ampli Yamaha"
                        loading={amps.isLoading}
                        tone={amps.data?.length ? "online" : "unknown"}
                        status={amps.data?.length ? plural(amps.data.length, "ampli configuré", "amplis configurés") : "Aucun ampli"}
                    />
                    <OverviewTile
                        href="/trash-guides"
                        icon={BookMarked}
                        iconClass="bg-amber-500/15 text-amber-300"
                        title="TRaSH Guides"
                        status="Profils par média & SABnzbd"
                    />
                    <OverviewTile
                        href="/remote"
                        icon={Sofa}
                        iconClass="bg-fuchsia-500/15 text-fuchsia-300"
                        title="Salon"
                        status="Télécommandes Kodi, ampli et Cast"
                    />
                </motion.div>
            </section>

            {/* ── Alerte sécurité (si le backend l'expose) ───── */}
            {settings?.auth.default_secret && (
                <motion.div
                    variants={fadeUp}
                    role="alert"
                    className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4"
                >
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
                    <div className="text-sm">
                        <p className="font-semibold text-amber-200">Mot de passe d&apos;administration par défaut</p>
                        <p className="mt-0.5 text-amber-100/80">
                            Change <code className="rounded bg-black/30 px-1 font-mono text-xs">ARRMADA_AUTH_SECRET</code> dans ton
                            fichier .env puis redémarre le conteneur : tant qu&apos;il garde la valeur d&apos;exemple, n&apos;importe qui sur
                            ton réseau peut se connecter.
                        </p>
                    </div>
                </motion.div>
            )}

            {isError ? (
                <motion.div variants={fadeUp} className="glass rounded-2xl">
                    <ErrorState error={error} onRetry={() => refetch()} title="Impossible de lire la configuration" />
                </motion.div>
            ) : isLoading || !settings ? (
                <motion.div variants={fadeUp} className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    {[0, 1].map((i) => (
                        <div key={i} className="glass space-y-3 rounded-2xl p-5">
                            <Shimmer className="h-4 w-40 rounded-md" />
                            {[0, 1, 2].map((j) => (
                                <Shimmer key={j} className="h-12 w-full" />
                            ))}
                        </div>
                    ))}
                </motion.div>
            ) : (
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                    {/* ── Telegram ─────────────────────────────── */}
                    <motion.div variants={fadeUp}>
                        <Panel
                            title="Notifications Telegram"
                            icon={BellRing}
                            iconClassName="text-sky-400"
                            className="h-full"
                            action={
                                <span
                                    className={cn(
                                        "flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold",
                                        settings.telegram.configured ? "bg-emerald-500/10 text-emerald-300" : "bg-slate-500/10 text-slate-300",
                                    )}
                                >
                                    <StatusDot tone={settings.telegram.configured ? "online" : "unknown"} size="sm" />
                                    {settings.telegram.configured ? "Actif" : "Inactif"}
                                </span>
                            }
                            bodyClassName="py-2"
                        >
                            <div className="divide-y divide-white/[0.05]">
                                <ConfigRow
                                    icon={KeyRound}
                                    label="Jeton du bot"
                                    tone={settings.telegram.bot_token_set ? "ok" : "warning"}
                                    value={
                                        settings.telegram.bot_token_set ? (
                                            "Défini dans le .env"
                                        ) : (
                                            <>
                                                Ajoute <code className="font-mono">TELEGRAM_BOT_TOKEN</code> au .env
                                            </>
                                        )
                                    }
                                />
                                <ConfigRow
                                    icon={Hash}
                                    label="Identifiant du chat"
                                    tone={settings.telegram.chat_id_set ? "ok" : "warning"}
                                    value={
                                        settings.telegram.chat_id_set ? (
                                            "Défini dans le .env"
                                        ) : (
                                            <>
                                                Ajoute <code className="font-mono">TELEGRAM_CHAT_ID</code> au .env
                                            </>
                                        )
                                    }
                                />
                            </div>
                            <div className="flex flex-wrap items-center gap-3 pb-2 pt-3">
                                <Button
                                    variant="glow"
                                    size="sm"
                                    onClick={handleTestTelegram}
                                    disabled={!settings.telegram.configured || testTelegram.isPending}
                                >
                                    {testTelegram.isPending ? <Loader2 className="animate-spin" /> : <Send />}
                                    Envoyer un test
                                </Button>
                                {!settings.telegram.configured && (
                                    <p className="text-xs text-muted-foreground">Renseigne les deux variables puis redémarre le backend.</p>
                                )}
                            </div>
                        </Panel>
                    </motion.div>

                    {/* ── Application ──────────────────────────── */}
                    <motion.div variants={fadeUp}>
                        <Panel title="Application" icon={ShieldCheck} iconClassName="text-emerald-400" className="h-full" bodyClassName="py-2">
                            <div className="divide-y divide-white/[0.05]">
                                <ConfigRow
                                    icon={ShieldCheck}
                                    label="Authentification"
                                    tone={settings.auth.default_secret ? "error" : "info"}
                                    badge={settings.auth.default_secret ? "Mot de passe par défaut" : undefined}
                                    value={`Session valable ${plural(settings.auth.jwt_expiration_hours, "heure")}`}
                                />
                                <ConfigRow
                                    icon={Film}
                                    label="TMDB (affiches, tendances)"
                                    tone={settings.tmdb.configured ? "ok" : "warning"}
                                    value={
                                        settings.tmdb.configured ? (
                                            "Clé API définie"
                                        ) : (
                                            <>
                                                Ajoute <code className="font-mono">TMDB_API_KEY</code> au .env
                                            </>
                                        )
                                    }
                                />
                                <ConfigRow
                                    icon={Globe}
                                    label="Origines autorisées (CORS)"
                                    tone="info"
                                    value={
                                        settings.cors.origins.length ? (
                                            <span className="font-mono" title={settings.cors.origins.join(", ")}>
                                                {settings.cors.origins.join(", ")}
                                            </span>
                                        ) : (
                                            "Aucune restriction déclarée"
                                        )
                                    }
                                />
                                <ConfigRow
                                    icon={Clock}
                                    label="Contrôles de santé"
                                    tone="info"
                                    value={`Toutes les ${settings.scheduler.health_check_interval.replace(/s$/, " s")}`}
                                />
                            </div>
                        </Panel>
                    </motion.div>
                </div>
            )}

            {/* ── À propos ───────────────────────────────────── */}
            <motion.div variants={fadeUp}>
                <SpotlightCard interactive={false} className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
                    <div className="relative z-[2] flex items-center gap-3">
                        <div className="h-11 w-11 shrink-0 overflow-hidden rounded-xl ring-1 ring-primary/30 shadow-[0_0_20px_-4px_hsl(var(--primary)/0.7)]">
                            <BrandIcon />
                        </div>
                        <div>
                            <p className="font-semibold">
                                Arr<span className="text-gradient">Mada</span>
                            </p>
                            <p className="text-xs text-muted-foreground">Le poste de commandement de ta stack *arr</p>
                        </div>
                    </div>
                    <div className="relative z-[2] flex flex-wrap gap-2 sm:ml-auto">
                        <span className="chip">
                            <Info className="h-3 w-3" /> Interface v{APP_VERSION}
                        </span>
                        <span className="chip">
                            <Server className="h-3 w-3" /> API {backendVersion ? `v${backendVersion}` : "—"}
                        </span>
                        {setup?.database_type && (
                            <span className="chip">
                                <Database className="h-3 w-3" /> {setup.database_type === "postgresql" ? "PostgreSQL" : "SQLite"}
                            </span>
                        )}
                    </div>
                </SpotlightCard>
            </motion.div>
        </motion.div>
    );
}
