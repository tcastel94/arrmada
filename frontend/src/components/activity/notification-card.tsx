"use client";

/**
 * Carte d'une notification.
 * ----------------------------------------------------------------
 * - Non lue : c'est un vrai <button> (clic / Entrée / Espace = marquer comme
 *   lue), avec pastille pulsée et liseré lumineux.
 * - Lue : simple bloc statique (plus rien à faire dessus).
 * - Alerte de service (hors ligne, rétabli, santé) : lien « Voir le
 *   service » placé HORS du bouton (pas d'éléments interactifs imbriqués).
 */
import Link from "next/link";
import { forwardRef } from "react";
import { motion } from "framer-motion";
import { ChevronRight, Loader2, Server } from "lucide-react";
import type { NotificationItem } from "@/hooks/use-notifications";
import { StatusDot } from "@/components/fx/status-dot";
import { formatLongDateTime, parseApiDate, timeAgo } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { cleanTitle, displayServiceName, isServiceAlert, severityMeta, typeIcon, typeLabel } from "./notification-meta";
import { formatTime, localDayKey } from "./day-groups";

interface NotificationCardProps {
    notif: NotificationItem;
    index: number;
    pending: boolean;
    onMarkRead: () => void;
}

export const NotificationCard = forwardRef<HTMLLIElement, NotificationCardProps>(function NotificationCard(
    { notif, index, pending, onMarkRead },
    ref,
) {
    const sev = severityMeta(notif.severity);
    const Icon = typeIcon(notif.type, sev.icon);
    const unread = !notif.is_read;
    const date = parseApiDate(notif.created_at);
    const title = cleanTitle(notif.title);
    const service = notif.service_name ? displayServiceName(notif.service_name) : null;
    const animated = index < 20;
    // Les cartes sont rangées sous un en-tête de jour : pour aujourd'hui on
    // affiche « il y a 5 min », sinon l'heure (« hier » de timeAgo signifie
    // « il y a 24-48 h » et contredirait l'en-tête « Jeudi 8 octobre »).
    const when = date ? (localDayKey(date) === localDayKey(new Date()) ? timeAgo(date) : formatTime(date)) : "";

    const content = (
        <>
            <span
                className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1", sev.tile, sev.text)}
                style={unread ? { boxShadow: `0 0 22px -6px ${sev.glow}` } : undefined}
            >
                <Icon className="h-[18px] w-[18px]" strokeWidth={1.9} />
            </span>

            <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-3">
                    <p className={cn("min-w-0 text-sm leading-snug", unread ? "font-semibold" : "font-medium text-foreground/75")}>{title}</p>
                    <time
                        dateTime={date?.toISOString()}
                        title={date ? formatLongDateTime(date) : undefined}
                        className="shrink-0 pt-0.5 text-[11px] tabular-nums text-muted-foreground/70"
                    >
                        {when}
                    </time>
                </div>
                {notif.message && (
                    <p className={cn("mt-1 line-clamp-3 whitespace-pre-line text-xs leading-relaxed", unread ? "text-muted-foreground" : "text-muted-foreground/70")}>
                        {notif.message}
                    </p>
                )}
                <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <span className={cn("inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-1.5 py-px text-[10px] font-semibold ring-1 ring-inset ring-white/[0.07]", sev.text)}>
                        <sev.icon className="h-2.5 w-2.5" />
                        {sev.label}
                    </span>
                    <span className="rounded-md bg-white/[0.04] px-1.5 py-px text-[10px] font-medium text-muted-foreground ring-1 ring-inset ring-white/[0.07]">
                        {typeLabel(notif.type)}
                    </span>
                    {service && (
                        <span className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-1.5 py-px text-[10px] font-medium text-muted-foreground ring-1 ring-inset ring-white/[0.07]">
                            <Server className="h-2.5 w-2.5" />
                            {service}
                        </span>
                    )}
                </div>
            </div>

            <span className="flex w-4 shrink-0 justify-center pt-1.5">
                {pending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                ) : unread ? (
                    <StatusDot tone={sev.dot} pulse size="md" />
                ) : null}
            </span>
        </>
    );

    return (
        <motion.li
            ref={ref}
            layout="position"
            initial={animated ? { opacity: 0, y: 12 } : { opacity: 0 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, transition: { duration: 0.2 } }}
            transition={{ duration: 0.4, ease: EASE_OUT, delay: animated ? index * 0.035 : 0 }}
            className="list-none"
        >
            <div
                className={cn(
                    "relative overflow-hidden rounded-2xl transition-[background-color,border-color,box-shadow] duration-500",
                    unread ? "glass glass-hover" : "border border-white/[0.04] bg-card/25",
                )}
            >
                {unread && (
                    <span aria-hidden className="absolute inset-y-0 left-0 w-[3px] bg-gradient-to-b from-rose-400 via-pink-400/70 to-primary/40" />
                )}
                {unread ? (
                    <button
                        type="button"
                        onClick={onMarkRead}
                        disabled={pending}
                        className="flex w-full items-start gap-3 p-4 text-left focus-visible:bg-white/[0.03] focus-visible:outline-none"
                    >
                        {content}
                        <span className="sr-only">— non lue, activer pour la marquer comme lue</span>
                    </button>
                ) : (
                    <div className="flex items-start gap-3 p-4">{content}</div>
                )}

                {isServiceAlert(notif.type) && (
                    <div className="flex justify-end border-t border-white/[0.04] px-4 py-2">
                        <Link
                            href="/settings/services"
                            className="group inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-primary"
                        >
                            Voir {service ? `le service ${service}` : "les services"}
                            <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
                        </Link>
                    </div>
                )}
            </div>
        </motion.li>
    );
});
