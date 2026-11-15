"use client";

// Rôle : fiches ouvertes au toucher depuis le repos : une sortie à venir,
// ou un téléchargement (vitesse, sources, relu toutes les 3 s).

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Loader2, WifiOff, X } from "lucide-react";
import { downloadStateLabel, formatEta, formatSize, formatSpeed, prettyTimeLeft, releaseTypeLabel, releaseWhen, type AmbientDownloadDetail, type AmbientUpcoming } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { RatingBadge } from "@/components/shared/rating-badge";
import { HttpError } from "../_lib/api";
import { u } from "../_lib/units";

/* ── Fiches au toucher (À venir, Téléchargement) ───────────── */

/** Cadre commun : voile, carte en bas de l'écran, fond flouté de l'image du titre. */
function DetailSheet({ fanart, onClose, children }: { fanart?: string; onClose: () => void; children: React.ReactNode }) {
    return (
        <motion.div
            // Rendue hors de la page (portail) : l'unité --u y est redéclarée
            className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 backdrop-blur-sm landscape:[--u:min(1vh,0.625vw)] portrait:[--u:min(0.625vh,1vw)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
        >
            <motion.div
                className="relative w-full overflow-hidden bg-[#1C1C1E]"
                style={{ maxWidth: u(120), margin: u(4), borderRadius: u(3), maxHeight: "86dvh" }}
                initial={{ y: 40, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 40, opacity: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 34 }}
                onClick={(event) => event.stopPropagation()}
            >
                {fanart && <div className="absolute inset-0 bg-cover bg-center opacity-20" style={{ backgroundImage: `url(${fanart})` }} />}
                <button
                    type="button"
                    onClick={onClose}
                    aria-label="Fermer"
                    className="absolute z-10 flex items-center justify-center rounded-full bg-black/50 text-white active:bg-black/70"
                    style={{ top: u(2), right: u(2), width: u(6), height: u(6) }}
                >
                    <X style={{ width: u(3.2), height: u(3.2) }} />
                </button>
                <div className="relative overflow-y-auto" style={{ padding: u(4), maxHeight: "86dvh" }}>
                    {children}
                </div>
            </motion.div>
        </motion.div>
    );
}

/** Une info de la fiche : petit libellé gris, valeur en dessous. */
function Fact({ label, value, accent }: { label: string; value: React.ReactNode; accent?: boolean }) {
    if (value === null || value === undefined || value === "") return null;
    return (
        <div className="min-w-0">
            <p className="uppercase text-slate-500" style={{ fontSize: u(2.1), letterSpacing: "0.12em" }}>
                {label}
            </p>
            <p className={cn("truncate tabular-nums", accent ? "text-[#8CC4FF]" : "text-slate-100")} style={{ fontSize: u(3.3), marginTop: u(0.4) }}>
                {value}
            </p>
        </div>
    );
}

export function UpcomingSheet({ item, now, onClose }: { item: AmbientUpcoming; now: Date; onClose: () => void }) {
    const when = releaseWhen(item.air_date, now, item.kind);
    const date = new Date(/^\d{4}-\d{2}-\d{2}$/.test(item.air_date) ? `${item.air_date}T12:00:00` : item.air_date);
    const fullDate = Number.isNaN(date.getTime())
        ? ""
        : new Intl.DateTimeFormat("fr-FR", { weekday: "long", day: "numeric", month: "long" }).format(date);
    const finale = item.finale_type === "series" ? "Dernier épisode de la série" : item.finale_type === "season" ? "Fin de saison" : "";
    return (
        <DetailSheet fanart={item.fanart} onClose={onClose}>
            <div className="flex" style={{ gap: u(4) }}>
                {item.poster && (
                    // eslint-disable-next-line @next/next/no-img-element -- affiche distante (Sonarr / Radarr)
                    <img src={item.poster} alt="" className="shrink-0 object-cover" style={{ width: u(20), aspectRatio: "2 / 3", borderRadius: u(1.4) }} />
                )}
                <div className="min-w-0 flex-1" style={{ paddingRight: u(6) }}>
                    <p className="text-[#8CC4FF] first-letter:uppercase" style={{ fontSize: u(2.8) }}>
                        {when}
                        {fullDate && when !== fullDate ? ` · ${fullDate}` : ""}
                    </p>
                    <p className="font-semibold text-white" style={{ fontSize: u(4.6), lineHeight: 1.15, marginTop: u(0.8) }}>
                        {item.title}
                    </p>
                    <p className="text-slate-300" style={{ fontSize: u(3.2), marginTop: u(0.8) }}>
                        {item.kind === "episode"
                            ? [item.label, item.subtitle].filter(Boolean).join(" · ")
                            : releaseTypeLabel(item.release_type) || item.label}
                    </p>
                    <div className="flex flex-wrap items-center" style={{ gap: u(1.2), marginTop: u(1.6) }}>
                        <RatingBadge value={item.rating} source={item.rating_source} className="text-[13px]" />
                        {finale && (
                            <span className="rounded-full bg-[#FF9F0A]/20 text-[#FFB340]" style={{ fontSize: u(2.4), padding: `${u(0.4)} ${u(1.4)}` }}>
                                {finale}
                            </span>
                        )}
                    </div>
                    {item.overview ? (
                        <p className="text-slate-300" style={{ fontSize: u(3), lineHeight: 1.45, marginTop: u(2) }}>
                            {item.overview}
                        </p>
                    ) : (
                        <p className="text-slate-500" style={{ fontSize: u(2.8), marginTop: u(2) }}>
                            Pas encore de résumé.
                        </p>
                    )}
                    <div className="grid grid-cols-3" style={{ gap: u(2.4), marginTop: u(2.6) }}>
                        <Fact label={item.kind === "episode" ? "Chaîne" : "Studio"} value={item.network} />
                        <Fact label="Durée" value={item.runtime ? `${item.runtime} min` : ""} />
                        <Fact label="Genre" value={(item.genres ?? []).join(", ")} />
                    </div>
                    <p className="text-slate-500" style={{ fontSize: u(2.5), marginTop: u(2.4) }}>
                        {item.monitored === false
                            ? "Non suivi : il ne sera pas téléchargé automatiquement."
                            : `Téléchargé automatiquement dès sa sortie par ${item.kind === "episode" ? "Sonarr" : "Radarr"}.`}
                    </p>
                </div>
            </div>
        </DetailSheet>
    );
}

/** Message d'une fiche de téléchargement qui n'a pas pu être lue (hors 404). */
function downloadErrorLabel(error: unknown): string {
    if (!(error instanceof HttpError)) return "Serveur injoignable, nouvel essai dans quelques secondes…";
    if (error.status === 401) return "Cet écran n'est plus appairé.";
    if (error.status === 403) return "Accès refusé à cet écran : mets ArrMada à jour ou appaire-le de nouveau.";
    if (error.status >= 500) return `Le serveur ne répond pas correctement (HTTP ${error.status}), nouvel essai…`;
    return `Fiche indisponible (HTTP ${error.status}).`;
}

export function DownloadSheet({
    downloadKey,
    title,
    load,
    onClose,
}: {
    downloadKey: string;
    title: string;
    load: (key: string) => Promise<AmbientDownloadDetail>;
    onClose: () => void;
}) {
    // Relue toutes les 3 s tant que la fiche est ouverte (vitesse, sources en direct)
    const { data: d, error } = useQuery({
        queryKey: ["ambient-download", downloadKey],
        queryFn: () => load(downloadKey),
        refetchInterval: 3_000,
        retry: false,
    });
    const live = d?.live ?? null;
    const torrent = d?.protocol === "torrent";
    const gone = error instanceof HttpError && error.status === 404;
    // Toute autre erreur est affichée (avant : « Chargement… » sans fin).
    // La fiche continue de réessayer toutes les 3 s.
    const failure = !d && error && !gone ? downloadErrorLabel(error) : "";
    const eta = formatEta(live?.eta_seconds) || (d?.time_left ? prettyTimeLeft(d.time_left) : "");
    const state = downloadStateLabel(live?.state || d?.status);
    const what =
        d?.kind === "series"
            ? [d.season != null ? `Saison ${d.season}` : "", d.episodes > 1 ? `${d.episodes} épisodes` : ""].filter(Boolean).join(" · ")
            : "";

    return (
        <DetailSheet fanart={d?.fanart} onClose={onClose}>
            <div className="flex" style={{ gap: u(4) }}>
                {d?.poster && (
                    // eslint-disable-next-line @next/next/no-img-element -- affiche distante (Sonarr / Radarr)
                    <img src={d.poster} alt="" className="shrink-0 object-cover" style={{ width: u(18), aspectRatio: "2 / 3", borderRadius: u(1.4) }} />
                )}
                <div className="min-w-0 flex-1" style={{ paddingRight: u(6) }}>
                    <p className="text-slate-400" style={{ fontSize: u(2.6) }}>
                        {state || "Téléchargement"}
                        {d?.client ? ` · ${d.client}` : ""}
                    </p>
                    <p className="font-semibold text-white" style={{ fontSize: u(4.6), lineHeight: 1.15, marginTop: u(0.8) }}>
                        {d?.title ?? title}
                    </p>
                    {what && (
                        <p className="text-slate-300" style={{ fontSize: u(3), marginTop: u(0.6) }}>
                            {what}
                        </p>
                    )}

                    {gone ? (
                        <p className="text-[#8CC4FF]" style={{ fontSize: u(3.2), marginTop: u(3) }}>
                            Terminé ou retiré de la file.
                        </p>
                    ) : failure ? (
                        <p className="flex items-center text-amber-300" style={{ fontSize: u(3), marginTop: u(3), gap: u(1.2) }}>
                            <WifiOff style={{ width: u(3.2), height: u(3.2) }} /> {failure}
                        </p>
                    ) : !d ? (
                        <p className="flex items-center text-slate-400" style={{ fontSize: u(3), marginTop: u(3), gap: u(1.2) }}>
                            <Loader2 className="animate-spin" style={{ width: u(3.2), height: u(3.2) }} /> Chargement…
                        </p>
                    ) : (
                        <>
                            {/* Progression */}
                            <div style={{ marginTop: u(2.4) }}>
                                <div className="flex items-baseline justify-between tabular-nums" style={{ fontSize: u(3) }}>
                                    <span className="text-slate-100">{d.progress.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %</span>
                                    <span className="text-slate-400">
                                        {formatSize(d.size_bytes - d.size_left_bytes)} / {formatSize(d.size_bytes)}
                                    </span>
                                </div>
                                <div className="overflow-hidden rounded-full bg-white/10" style={{ height: u(1.1), marginTop: u(1) }}>
                                    <motion.div
                                        className="h-full rounded-full bg-[#4A9EFF]"
                                        initial={false}
                                        animate={{ width: `${d.progress}%` }}
                                        transition={{ duration: 0.6, ease: "easeOut" }}
                                    />
                                </div>
                            </div>

                            {/* Chiffres clés */}
                            <div className="grid grid-cols-3" style={{ gap: u(2.4), marginTop: u(2.8) }}>
                                <Fact label="Vitesse" value={live ? formatSpeed(live.download_speed) : "—"} accent />
                                <Fact label="Reste" value={eta || "—"} />
                                {torrent ? (
                                    <Fact
                                        label="Sources"
                                        value={live ? `${live.seeds ?? 0}${live.seeds_total ? ` (${live.seeds_total})` : ""}` : "—"}
                                    />
                                ) : (
                                    <Fact label="Dans la file" value={live?.position ? `${live.position} / ${live.queue_size}` : "—"} />
                                )}
                                {torrent && <Fact label="Pairs" value={live ? `${live.peers ?? 0}${live.peers_total ? ` (${live.peers_total})` : ""}` : ""} />}
                                {torrent && <Fact label="Envoi" value={live?.upload_speed ? formatSpeed(live.upload_speed) : ""} />}
                                {torrent && <Fact label="Ratio" value={live?.ratio != null ? live.ratio.toLocaleString("fr-FR") : ""} />}
                                {!torrent && <Fact label="Ancienneté" value={live?.age} />}
                                {!torrent && <Fact label="Priorité" value={live?.priority} />}
                                <Fact label="Qualité" value={d.quality} />
                                <Fact label="Indexeur" value={d.indexer.replace(/\s*\(Prowlarr\)$/i, "")} />
                                <Fact label={torrent ? "Tracker" : "Protocole"} value={torrent ? live?.tracker : "Usenet"} />
                            </div>

                            {(d.error || d.detail || d.live_hint) && (
                                <p
                                    className={d.error ? "text-[#FF6961]" : "text-slate-400"}
                                    style={{ fontSize: u(2.7), marginTop: u(2.4) }}
                                >
                                    {d.error || d.detail || d.live_hint}
                                </p>
                            )}
                            {d.release && (
                                <p className="truncate font-mono text-slate-600" style={{ fontSize: u(2.2), marginTop: u(2) }}>
                                    {d.release}
                                </p>
                            )}
                        </>
                    )}
                </div>
            </div>
        </DetailSheet>
    );
}
