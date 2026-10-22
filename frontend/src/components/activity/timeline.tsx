"use client";

/**
 * Timeline verticale du Journal d'activité.
 * ----------------------------------------------------------------
 * - Regroupée par jour LOCAL (« Aujourd'hui », « Hier », « Mardi 7 octobre »).
 * - Chaque évènement : pastille lumineuse à la couleur de sa catégorie posée
 *   sur une ligne de temps dégradée ; la ligne entière mène à la fiche média
 *   quand l'évènement en porte une.
 * - Les échecs ont un bouton « Détails » qui déplie le message d'erreur
 *   (bouton séparé du lien : pas d'éléments interactifs imbriqués).
 * - Cascade d'entrée limitée aux ~20 premières lignes (au-delà : fondu
 *   simple, sinon « Charger plus » ferait attendre plusieurs secondes).
 */
/* eslint-disable @next/next/no-img-element */
import Link from "next/link";
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ChevronRight, Film, Tv } from "lucide-react";
import type { TimelineGroup, TimelineItem } from "@/hooks/use-activity";
import { SpotlightCard } from "@/components/fx/spotlight-card";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { formatBytes, formatDuration, formatLongDateTime, plural, timeAgo } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { actionIcon, actionLabel, categoryMeta, sourceLabel, timelineHref } from "./activity-meta";
import { formatTime, groupByDay } from "./day-groups";

const STAGGER_LIMIT = 20;

function tsDate(item: Pick<TimelineItem, "ts">): Date | null {
    return item.ts ? new Date(item.ts * 1000) : null;
}

/* ── Vue chronologique ──────────────────────────────────────── */

export function ActivityTimeline({ items }: { items: TimelineItem[] }) {
    const groups = useMemo(() => groupByDay(items, tsDate), [items]);

    // Index global de chaque ligne (pour limiter la cascade aux premières).
    let running = 0;

    return (
        <div className="space-y-6">
            {groups.map((g) => {
                const failures = g.items.filter((it) => it.status === "ko").length;
                return (
                    <section key={g.key} aria-label={g.label}>
                        <div className="mb-2.5 flex items-center gap-3 px-1">
                            <h2 className="text-sm font-semibold tracking-tight">{g.label}</h2>
                            <span className="text-[11px] tabular-nums text-muted-foreground">
                                {plural(g.items.length, "évènement")}
                                {failures > 0 && <span className="text-destructive"> · {plural(failures, "échec")}</span>}
                            </span>
                            <span aria-hidden className="h-px flex-1 bg-gradient-to-r from-white/10 to-transparent" />
                        </div>
                        <SpotlightCard interactive={false} className="relative p-1.5 sm:p-2">
                            {/* Ligne de temps dégradée qui relie les pastilles */}
                            <span
                                aria-hidden
                                className="pointer-events-none absolute bottom-6 left-[31.5px] top-6 w-px bg-gradient-to-b from-emerald-400/50 via-primary/25 to-transparent sm:left-[35.5px]"
                            />
                            <ol className="relative">
                                {g.items.map((it) => {
                                    const index = running++;
                                    return <TimelineRow key={it.id} item={it} index={index} />;
                                })}
                            </ol>
                        </SpotlightCard>
                    </section>
                );
            })}
        </div>
    );
}

function TimelineRow({ item, index, compact = false }: { item: TimelineItem; index: number; compact?: boolean }) {
    const [open, setOpen] = useState(false);
    const cat = categoryMeta(item.category);
    const Icon = actionIcon(item);
    const href = timelineHref(item);
    const failed = item.status === "ko";
    const date = tsDate(item);
    const canExpand = failed && !!item.detail;

    const meta = [
        item.subtitle,
        !failed ? item.detail : null,
        item.device ? `sur ${item.device}` : null,
        item.size_bytes ? formatBytes(item.size_bytes) : null,
        item.duration_ms ? formatDuration(item.duration_ms / 1000) : null,
    ].filter(Boolean) as string[];

    const body = (
        <>
            {/* Pastille lumineuse */}
            <span
                className={cn(
                    "relative z-[1] flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 sm:h-10 sm:w-10",
                    failed ? "from-red-500/35 to-rose-500/10 text-destructive ring-destructive/40" : cn(cat.tile, cat.text),
                )}
                style={{ boxShadow: `0 0 22px -6px ${failed ? "hsl(0 84% 62% / 0.6)" : cat.glow}` }}
            >
                <Icon className="h-4 w-4" strokeWidth={2} />
                {item.status === "ok" && !compact && (
                    <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-success ring-2 ring-background" />
                )}
            </span>

            {!compact && item.poster_url && (
                <img
                    src={item.poster_url}
                    alt=""
                    loading="lazy"
                    className="hidden h-11 w-8 shrink-0 rounded-md object-cover ring-1 ring-white/10 sm:block"
                />
            )}

            <div className="min-w-0 flex-1">
                <p className="truncate text-sm">
                    <span className={cn("font-semibold", failed && "text-destructive")}>{actionLabel(item.action, item.status)}</span>
                    {item.title && !compact && <span className="text-muted-foreground"> · {item.title}</span>}
                </p>
                <div className="mt-0.5 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[11px] text-muted-foreground/80">
                    {meta.map((m, i) => (
                        <span key={`${i}-${m}`} className="max-w-full truncate">
                            {i > 0 && <span className="mr-1.5 text-muted-foreground/40">·</span>}
                            {m}
                        </span>
                    ))}
                    <span className="rounded-md bg-white/[0.05] px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide ring-1 ring-inset ring-white/[0.07]">
                        {sourceLabel(item.source)}
                    </span>
                </div>
            </div>

            <time
                dateTime={date?.toISOString()}
                title={date ? `${formatLongDateTime(date)} (${timeAgo(date)})` : undefined}
                className="shrink-0 pt-0.5 text-[11px] tabular-nums text-muted-foreground/70"
            >
                {date ? (compact ? timeAgo(date, { short: true }) : formatTime(date)) : ""}
            </time>
            {href && (
                <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground/30 transition-all group-hover:translate-x-0.5 group-hover:text-primary" />
            )}
        </>
    );

    const animated = index < STAGGER_LIMIT;

    return (
        <motion.li
            initial={animated ? { opacity: 0, x: -14 } : { opacity: 0 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: animated ? 0.4 : 0.25, ease: EASE_OUT, delay: animated ? index * 0.03 : 0 }}
            className="relative"
        >
            {href ? (
                <Link
                    href={href}
                    className="group flex items-start gap-3 rounded-xl px-2 py-2 transition-colors hover:bg-white/[0.035] focus-visible:bg-white/[0.05] focus-visible:outline-none"
                >
                    {body}
                </Link>
            ) : (
                <div className="group flex items-start gap-3 rounded-xl px-2 py-2">{body}</div>
            )}

            {canExpand && (
                <div className="pb-2 pl-14 pr-2 sm:pl-[60px]">
                    <button
                        type="button"
                        onClick={() => setOpen((o) => !o)}
                        aria-expanded={open}
                        className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium text-destructive/90 transition-colors hover:bg-destructive/10 hover:text-destructive"
                    >
                        {open ? "Masquer les détails" : "Détails de l'échec"}
                        <ChevronDown className={cn("h-3 w-3 transition-transform duration-300", open && "rotate-180")} />
                    </button>
                    <AnimatePresence initial={false}>
                        {open && (
                            <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: "auto", opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.3, ease: EASE_OUT }}
                                className="overflow-hidden"
                            >
                                <p className="mt-1.5 whitespace-pre-wrap break-words rounded-lg border border-destructive/20 bg-destructive/[0.07] px-2.5 py-2 font-mono text-[11px] leading-relaxed text-destructive/90">
                                    {item.detail}
                                </p>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            )}
        </motion.li>
    );
}

/* ── Vue « par média » ──────────────────────────────────────── */

const GROUP_PREVIEW = 5;

export function MediaGroups({ groups }: { groups: TimelineGroup[] }) {
    return (
        <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
            {groups.map((g, i) => (
                <MediaGroupCard key={g.key} group={g} index={i} />
            ))}
        </div>
    );
}

function MediaGroupCard({ group, index }: { group: TimelineGroup; index: number }) {
    const [expanded, setExpanded] = useState(false);
    const href = timelineHref(group);
    const Placeholder = group.media_type === "series" ? Tv : Film;
    const shown = expanded ? group.items : group.items.slice(0, GROUP_PREVIEW);
    const hidden = group.items.length - shown.length;
    const last = group.last_ts ? new Date(group.last_ts * 1000) : null;
    const animated = index < STAGGER_LIMIT;

    const header = (
        <>
            {group.poster_url ? (
                <img src={group.poster_url} alt="" loading="lazy" className="h-14 w-10 shrink-0 rounded-lg object-cover ring-1 ring-white/10" />
            ) : (
                <span className="flex h-14 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/40 ring-1 ring-white/[0.06]">
                    <Placeholder className="h-4 w-4 text-muted-foreground/50" />
                </span>
            )}
            <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold transition-colors group-hover:text-primary">{group.title}</p>
                <p className="text-[11px] text-muted-foreground">
                    {plural(group.count, "évènement")}
                    {last && <> · {timeAgo(last)}</>}
                </p>
            </div>
            {href && <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground/40 transition-transform group-hover:translate-x-0.5" />}
        </>
    );

    return (
        <motion.div
            initial={animated ? { opacity: 0, y: 14 } : { opacity: 0 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: EASE_OUT, delay: animated ? index * 0.04 : 0 }}
        >
            <SpotlightCard interactive={false} className="h-full p-2">
                {href ? (
                    <Link href={href} className="group flex items-center gap-3 rounded-xl p-2 transition-colors hover:bg-white/[0.03]">
                        {header}
                    </Link>
                ) : (
                    <div className="group flex items-center gap-3 p-2">{header}</div>
                )}
                <ol className="mt-1 border-t border-white/[0.05] pt-1">
                    {shown.map((it, i) => (
                        <TimelineRow key={it.id} item={it} index={STAGGER_LIMIT + i} compact />
                    ))}
                </ol>
                {group.items.length > GROUP_PREVIEW && (
                    <button
                        type="button"
                        onClick={() => setExpanded((e) => !e)}
                        aria-expanded={expanded}
                        className="mt-1 w-full rounded-lg py-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.03] hover:text-foreground"
                    >
                        {expanded ? "Réduire" : `Voir ${plural(hidden, "autre évènement", "autres évènements")}`}
                    </button>
                )}
            </SpotlightCard>
        </motion.div>
    );
}

/* ── Squelette ──────────────────────────────────────────────── */

export function TimelineSkeleton() {
    return (
        <div className="space-y-6" aria-busy aria-label="Chargement du journal">
            {[5, 3].map((rows, s) => (
                <div key={s}>
                    <Shimmer className="mb-3 h-4 w-32 rounded-md" />
                    <div className="glass space-y-1 rounded-2xl p-3">
                        {Array.from({ length: rows }).map((_, i) => (
                            <div key={i} className="flex items-center gap-3 py-1.5">
                                <Shimmer className="h-10 w-10 rounded-xl" />
                                <div className="flex-1 space-y-2">
                                    <Shimmer className="h-3.5 w-2/3 rounded-md" />
                                    <Shimmer className="h-2.5 w-1/3 rounded-md" />
                                </div>
                                <Shimmer className="h-3 w-10 rounded-md" />
                            </div>
                        ))}
                    </div>
                </div>
            ))}
        </div>
    );
}
