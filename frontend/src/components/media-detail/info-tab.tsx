"use client";

/**
 * Onglet « Infos » : détails (statut traduit, studio/chaîne, dates…),
 * emplacement sur le disque (copie + bouton Déplacer), identifiants
 * externes (copie + lien) et tags.
 */
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
    Building2,
    Calendar,
    Clock,
    Copy,
    ExternalLink,
    Eye,
    Fingerprint,
    FolderInput,
    FolderOpen,
    HardDrive,
    Info,
    Layers,
    ShieldCheck,
    Tags,
    Tv,
} from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { useMediaEditOptions, type MediaDetail } from "@/hooks/use-media";
import { formatBytes, formatDuration, parseApiDate } from "@/lib/format";
import { fadeUp, stagger } from "@/lib/motion";
import { availabilityLabel, copyText, seriesTypeLabel, statusInfo } from "./labels";

function Item({ icon: Icon, label, value }: { icon: typeof Info; label: string; value?: React.ReactNode }) {
    if (value === undefined || value === null || value === "") return null;
    return (
        <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] ring-1 ring-white/[0.06]">
                <Icon className="h-3.5 w-3.5 text-primary/80" aria-hidden />
            </span>
            <div className="min-w-0">
                <dt className="eyebrow">{label}</dt>
                <dd className="mt-0.5 break-words text-sm font-medium">{value}</dd>
            </div>
        </div>
    );
}

/** « 1 juin 2024 » : l'année compte pour une date d'ajout (formatLongDateTime l'omet). */
function fullDate(value: string | null | undefined): string | undefined {
    const d = parseApiDate(value);
    return d ? d.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }) : undefined;
}

async function copy(value: string, what: string) {
    if (await copyText(value)) toast.success(`${what} copié`);
    else toast.error("Copie impossible", { description: "Ton navigateur bloque l'accès au presse-papiers." });
}

export function InfoTab({ media, onMove }: { media: MediaDetail; onMove: () => void }) {
    const isMovie = media.type === "movie";
    const status = statusInfo(media.status, media.type);
    const options = useMediaEditOptions(media.type, (media.tags?.length ?? 0) > 0);
    const tagNames = (media.tags ?? []).map((id) => options.data?.tags.find((t) => t.id === id)?.label ?? `#${id}`);

    const ids: { label: string; value: string; href?: string }[] = [];
    if (media.tmdb_id) ids.push({ label: "TMDb", value: String(media.tmdb_id), href: `https://www.themoviedb.org/movie/${media.tmdb_id}` });
    if (media.tvdb_id) ids.push({ label: "TVDB", value: String(media.tvdb_id), href: `https://www.thetvdb.com/dereferrer/series/${media.tvdb_id}` });
    if (media.imdb_id) ids.push({ label: "IMDb", value: media.imdb_id, href: `https://www.imdb.com/title/${media.imdb_id}` });
    ids.push({ label: isMovie ? "Radarr" : "Sonarr", value: String(media.id) });

    return (
        <motion.div variants={stagger(0, 0.07)} initial="hidden" animate="show" className="grid items-start gap-6 lg:grid-cols-3">
            <motion.div variants={fadeUp} className="lg:col-span-2">
                <Panel title="Détails" icon={Info}>
                    <dl className="grid gap-5 sm:grid-cols-2">
                        <Item icon={Eye} label="Statut" value={status?.label} />
                        <Item icon={isMovie ? Building2 : Tv} label={isMovie ? "Studio" : "Chaîne"} value={isMovie ? media.studio : media.network} />
                        <Item icon={Calendar} label="Année" value={media.year || undefined} />
                        <Item
                            icon={Clock}
                            label={isMovie ? "Durée" : "Durée d'un épisode"}
                            value={media.runtime ? formatDuration(media.runtime * 60) : undefined}
                        />
                        <Item icon={ShieldCheck} label="Certification" value={media.certification} />
                        {isMovie ? (
                            <Item icon={Layers} label="Disponibilité minimale" value={media.minimum_availability ? availabilityLabel(media.minimum_availability) : undefined} />
                        ) : (
                            <Item icon={Layers} label="Type de série" value={media.series_type ? seriesTypeLabel(media.series_type) : undefined} />
                        )}
                        <Item icon={HardDrive} label="Taille sur le disque" value={media.size_on_disk > 0 ? formatBytes(media.size_on_disk) : "—"} />
                        <Item icon={Calendar} label="Ajouté le" value={fullDate(media.added)} />
                    </dl>
                </Panel>
            </motion.div>

            <motion.div variants={fadeUp} className="space-y-6">
                <Panel title="Identifiants" icon={Fingerprint}>
                    <ul className="space-y-2">
                        {ids.map((id) => (
                            <li key={id.label} className="flex items-center gap-2">
                                <span className="w-16 shrink-0 text-xs text-muted-foreground">{id.label}</span>
                                <code className="min-w-0 flex-1 truncate font-mono text-sm">{id.value}</code>
                                <Button size="icon-sm" variant="ghost" aria-label={`Copier l'identifiant ${id.label}`} onClick={() => copy(id.value, `Identifiant ${id.label}`)}>
                                    <Copy />
                                </Button>
                                {id.href && (
                                    <Button size="icon-sm" variant="ghost" asChild>
                                        <a href={id.href} target="_blank" rel="noopener noreferrer" aria-label={`Ouvrir sur ${id.label} (nouvel onglet)`}>
                                            <ExternalLink />
                                        </a>
                                    </Button>
                                )}
                            </li>
                        ))}
                    </ul>
                </Panel>

                {(media.tags?.length ?? 0) > 0 && (
                    <Panel title="Tags" icon={Tags}>
                        {options.isLoading ? (
                            <div className="flex gap-1.5">
                                <Shimmer className="h-6 w-16 rounded-full" />
                                <Shimmer className="h-6 w-20 rounded-full" />
                            </div>
                        ) : (
                            <div className="flex flex-wrap gap-1.5">
                                {tagNames.map((t) => (
                                    <span key={t} className="chip">
                                        {t}
                                    </span>
                                ))}
                            </div>
                        )}
                    </Panel>
                )}
            </motion.div>

            <motion.div variants={fadeUp} className="lg:col-span-3">
                <Panel
                    title="Emplacement"
                    icon={FolderOpen}
                    iconClassName="text-primary"
                    action={
                        <Button size="sm" variant="outline" onClick={onMove}>
                            <FolderInput /> Déplacer…
                        </Button>
                    }
                >
                    <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                        <code className="min-w-0 flex-1 break-all font-mono text-xs text-foreground/80">{media.path || "—"}</code>
                        {media.path && (
                            <Button size="icon-sm" variant="ghost" aria-label="Copier le chemin" onClick={() => copy(media.path, "Chemin")}>
                                <Copy />
                            </Button>
                        )}
                    </div>
                </Panel>
            </motion.div>
        </motion.div>
    );
}
