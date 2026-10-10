"use client";

/**
 * Puces de sous-titres (présent / manquant) partagées par les panneaux
 * film et série.
 * Code couleur : vert = présent, ambre = manquant (jamais rouge : le rouge
 * est réservé aux erreurs).
 * Vocabulaire : « forced » → « forcés », « HI » → « SDH » (sous-titres pour
 * sourds et malentendants), piste sans fichier externe → « intégré ».
 */
import { CircleAlert, CircleCheck, Loader2, Trash2, Wand2 } from "lucide-react";
import type { SubtitleTrack } from "@/hooks/use-subtitles";
import { cn } from "@/lib/utils";
import { subLangLabel } from "../labels";

function Flags({ track }: { track: SubtitleTrack }) {
    return (
        <>
            {track.forced && <span className="rounded bg-white/10 px-1 text-[9px] font-semibold uppercase tracking-wide">forcés</span>}
            {track.hi && (
                <abbr title="Sous-titres pour sourds et malentendants" className="rounded bg-white/10 px-1 text-[9px] font-semibold no-underline">
                    SDH
                </abbr>
            )}
        </>
    );
}

export function SubTrackChip({
    track,
    onDelete,
    deleting,
    onSync,
    syncing,
    className,
}: {
    track: SubtitleTrack;
    onDelete?: () => void;
    deleting?: boolean;
    onSync?: () => void;
    syncing?: boolean;
    className?: string;
}) {
    // Une piste sans chemin est intégrée au fichier vidéo : ni supprimable ni synchronisable.
    const external = !!track.path;
    const lang = subLangLabel(track);
    return (
        <span
            className={cn(
                "inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 py-0.5 pl-2 pr-1 text-xs text-emerald-300",
                !external && "pr-2",
                className,
            )}
        >
            <CircleCheck className="h-3.5 w-3.5" aria-hidden />
            {lang}
            <Flags track={track} />
            {!external && <span className="text-[9px] opacity-70">intégré</span>}
            {external && onSync && !track.forced && (
                <button
                    type="button"
                    onClick={onSync}
                    disabled={syncing}
                    aria-label={`Synchroniser le sous-titre ${lang} sur l'audio de la vidéo`}
                    title="Caler sur la vidéo (synchronise le timing sur l'audio)"
                    className="ml-0.5 flex h-5 w-5 items-center justify-center rounded-full text-emerald-300/70 transition-colors hover:bg-sky-500/15 hover:text-sky-300 disabled:opacity-50"
                >
                    {syncing ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wand2 className="h-3 w-3" />}
                </button>
            )}
            {external && onDelete && (
                <button
                    type="button"
                    onClick={onDelete}
                    disabled={deleting}
                    aria-label={`Supprimer le sous-titre ${lang}`}
                    title="Supprimer ce sous-titre"
                    className="flex h-5 w-5 items-center justify-center rounded-full text-emerald-300/70 transition-colors hover:bg-red-500/15 hover:text-red-300 disabled:opacity-50"
                >
                    {deleting ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                </button>
            )}
        </span>
    );
}

export function MissingSubChip({ track }: { track: SubtitleTrack }) {
    return (
        <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">
            <CircleAlert className="h-3.5 w-3.5" aria-hidden />
            {subLangLabel(track)}
            <Flags track={track} />
        </span>
    );
}
