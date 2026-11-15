"use client";

// Rôle : panneaux du bas de l'écran au repos : sorties à venir,
// téléchargements en cours et ampli de la pièce.

import { CalendarClock, Download, Speaker, VolumeX } from "lucide-react";
import { prettyName, prettyTimeLeft, releaseTypeLabel, releaseWhen, type Ambient, type AmbientUpcoming } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { u } from "../_lib/units";

function Panel({
    icon: Icon,
    title,
    className,
    children,
}: {
    icon: typeof Speaker;
    title: string;
    className?: string;
    children: React.ReactNode;
}) {
    return (
        <section
            className={cn("min-w-0 border border-white/[0.07] bg-white/[0.03]", className)}
            style={{ padding: u(2.8), borderRadius: u(2) }}
        >
            <p
                className="flex items-center uppercase text-slate-500"
                style={{ fontSize: u(2.6), gap: u(1.2), letterSpacing: "0.18em", marginBottom: u(2) }}
            >
                <Icon style={{ width: u(2.8), height: u(2.8) }} /> {title}
            </p>
            {children}
        </section>
    );
}

export function UpcomingPanel({
    upcoming,
    now,
    onOpen,
}: {
    upcoming: Ambient["upcoming"];
    now: Date;
    onOpen: (item: AmbientUpcoming) => void;
}) {
    return (
        <Panel icon={CalendarClock} title="À venir" className="flex-[1.7]">
            <ul className="flex flex-col" style={{ gap: u(0.6), fontSize: u(3.4) }}>
                {upcoming.map((item, i) => (
                    <li key={`${item.title}-${item.label}-${i}`}>
                        {/* Toute la ligne se touche : fiche de la sortie */}
                        <button
                            type="button"
                            onClick={() => onOpen(item)}
                            className="flex w-full items-baseline justify-between rounded-lg text-left transition-colors active:bg-white/[0.08]"
                            style={{ gap: u(2), padding: `${u(0.6)} ${u(0.8)}`, margin: `0 calc(${u(0.8)} * -1)` }}
                        >
                            <span className="min-w-0 truncate">
                                <span className="text-slate-100">{item.title}</span>
                                <span className="text-slate-500">
                                    {" "}
                                    {item.kind === "episode" ? item.label : releaseTypeLabel(item.release_type) || item.label}
                                </span>
                            </span>
                            <span className="shrink-0 text-[#8CC4FF]">{releaseWhen(item.air_date, now, item.kind)}</span>
                        </button>
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

export function DownloadsPanel({ downloads, onOpen }: { downloads: Ambient["downloads"]; onOpen: (key: string, title: string) => void }) {
    return (
        <Panel icon={Download} title="Téléchargements" className="flex-[1.3]">
            <ul className="flex flex-col" style={{ gap: u(1), fontSize: u(3.2) }}>
                {downloads.map((d, i) => (
                    <li key={`${d.key ?? d.title}-${i}`}>
                        <button
                            type="button"
                            // Serveur ancien (sans clé) : pas de fiche
                            disabled={!d.key}
                            onClick={() => d.key && onOpen(d.key, d.title)}
                            className="flex w-full flex-col rounded-lg text-left transition-colors active:bg-white/[0.08] disabled:active:bg-transparent"
                            style={{ gap: u(0.9), padding: `${u(0.6)} ${u(0.8)}`, margin: `0 calc(${u(0.8)} * -1)` }}
                        >
                            <div className="flex w-full items-baseline justify-between" style={{ gap: u(2) }}>
                                <span className="truncate text-slate-100">{d.title}</span>
                                <span className="shrink-0 tabular-nums text-slate-400">
                                    {d.paused ? "en pause" : d.time_left ? prettyTimeLeft(d.time_left) : `${d.progress} %`}
                                </span>
                            </div>
                            <div className="w-full overflow-hidden rounded-full bg-white/10" style={{ height: u(0.9) }}>
                                <div className={cn("h-full rounded-full", d.paused ? "bg-slate-500" : "bg-[#4A9EFF]")} style={{ width: `${d.progress}%` }} />
                            </div>
                        </button>
                    </li>
                ))}
            </ul>
        </Panel>
    );
}

export function AmpPanel({ amp }: { amp: NonNullable<Ambient["amp"]> }) {
    const on = amp.power === "on";
    return (
        <Panel icon={Speaker} title={amp.name || "Ampli"} className="flex-[0.9]">
            {on ? (
                <div className="flex flex-col" style={{ gap: u(1) }}>
                    <p className="flex items-center leading-none tabular-nums text-slate-100" style={{ fontSize: u(9), gap: u(1.2) }}>
                        {amp.mute ? <VolumeX className="text-amber-300" style={{ width: u(6), height: u(6) }} /> : null}
                        {amp.volume_pct ?? "—"}
                        <span className="text-slate-500" style={{ fontSize: u(4) }}>
                            %
                        </span>
                    </p>
                    <p className="truncate text-slate-300" style={{ fontSize: u(3.2) }}>
                        {prettyName(amp.input) || "—"}
                    </p>
                    <p className="truncate text-slate-500" style={{ fontSize: u(2.8) }}>
                        {prettyName(amp.sound_program)}
                    </p>
                </div>
            ) : (
                <p className="text-slate-500" style={{ fontSize: u(3.2) }}>
                    En veille
                </p>
            )}
        </Panel>
    );
}
