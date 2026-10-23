"use client";

/**
 * Onglet « Casting » : équipe technique (métiers traduits) + grille
 * d'avatars ronds avec halo lumineux au survol. Un clic ouvre la
 * filmographie de l'acteur (PersonDialog).
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { motion } from "framer-motion";
import { Clapperboard, Users } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState } from "@/components/shared/empty-state";
import type { CastMember } from "@/hooks/use-media";
import { scaleIn, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { crewLabel, initials } from "./labels";
import { PersonDialog } from "./person-dialog";

export function CastSection({ cast = [], crew = [] }: { cast?: CastMember[]; crew?: CastMember[] }) {
    const [selected, setSelected] = useState<{ id: number; name: string; photo?: string | null } | null>(null);

    if (cast.length === 0 && crew.length === 0) {
        return (
            <EmptyState
                icon={Users}
                title="Pas d'informations de casting"
                description="Radarr / Sonarr n'a fourni aucun acteur ni membre d'équipe pour ce titre."
            />
        );
    }

    // Équipe regroupée par métier : « Réalisation : A, B ».
    const crewByJob = new Map<string, string[]>();
    for (const member of crew) {
        const job = crewLabel(member);
        const names = crewByJob.get(job) ?? [];
        if (!names.includes(member.name)) names.push(member.name);
        crewByJob.set(job, names);
    }

    return (
        <div className="space-y-6">
            {crewByJob.size > 0 && (
                <Panel title="Équipe" icon={Clapperboard} iconClassName="text-primary">
                    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                        {Array.from(crewByJob.entries()).map(([job, names]) => (
                            <div key={job} className="space-y-0.5">
                                <dt className="eyebrow">{job}</dt>
                                <dd className="text-sm font-medium">{names.join(", ")}</dd>
                            </div>
                        ))}
                    </dl>
                </Panel>
            )}

            {cast.length > 0 && (
                <Panel
                    title="Casting"
                    icon={Users}
                    action={<span className="hidden text-xs text-muted-foreground sm:inline">Clique sur un visage pour sa filmographie</span>}
                >
                    <motion.ul
                        variants={stagger(0, 0.03)}
                        initial="hidden"
                        animate="show"
                        className="grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 2xl:grid-cols-10"
                    >
                        {cast.map((actor, i) => (
                            <motion.li
                                key={`${actor.tmdb_id ?? actor.name}-${actor.character}`}
                                variants={i < 24 ? scaleIn : undefined}
                            >
                                <ActorAvatar
                                    actor={actor}
                                    onOpen={() =>
                                        actor.tmdb_id && setSelected({ id: actor.tmdb_id, name: actor.name, photo: actor.photo })
                                    }
                                />
                            </motion.li>
                        ))}
                    </motion.ul>
                </Panel>
            )}

            <PersonDialog person={selected} onClose={() => setSelected(null)} />
        </div>
    );
}

function ActorAvatar({ actor, onOpen }: { actor: CastMember; onOpen: () => void }) {
    const clickable = !!actor.tmdb_id;
    const [failed, setFailed] = useState(false);
    return (
        <button
            type="button"
            disabled={!clickable}
            onClick={onOpen}
            aria-label={clickable ? `Voir la filmographie de ${actor.name}` : undefined}
            className="group flex w-full flex-col items-center gap-2 rounded-xl text-center focus-visible:outline-none disabled:cursor-default"
        >
            <span className="relative">
                {/* Halo lumineux au survol / focus clavier */}
                <span
                    aria-hidden
                    className={cn(
                        "absolute -inset-1.5 rounded-full bg-gradient-to-br from-primary via-primary to-brand opacity-0 blur-md transition-opacity duration-500",
                        clickable && "group-hover:opacity-70 group-focus-visible:opacity-90",
                    )}
                />
                <span
                    className={cn(
                        "relative flex h-[4.5rem] w-[4.5rem] items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-muted to-primary/20 ring-2 ring-white/10 transition-all duration-500 ease-smooth sm:h-20 sm:w-20",
                        clickable && "group-hover:scale-105 group-hover:ring-primary/60 group-focus-visible:ring-primary",
                    )}
                >
                    {actor.photo && !failed ? (
                        <img
                            src={actor.photo}
                            alt=""
                            loading="lazy"
                            onError={() => setFailed(true)}
                            className="h-full w-full object-cover transition-transform duration-700 ease-smooth group-hover:scale-110"
                        />
                    ) : (
                        <span className="text-base font-semibold text-foreground/70">{initials(actor.name)}</span>
                    )}
                </span>
            </span>
            <span className="w-full min-w-0">
                <span className="block truncate text-xs font-semibold transition-colors group-hover:text-primary sm:text-sm">{actor.name}</span>
                {actor.character && <span className="block truncate text-[11px] text-muted-foreground">{actor.character}</span>}
            </span>
        </button>
    );
}
