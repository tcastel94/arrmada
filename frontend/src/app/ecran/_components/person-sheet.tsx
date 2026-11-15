"use client";

// Rôle : filmographie d'un acteur touché dans la fiche du film en cours.

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import type { PersonFilmography } from "@/lib/ambient";
import { cn } from "@/lib/utils";
import { u } from "../_lib/units";

/**
 * Filmographie d'un acteur : ses films de la médiathèque en premier, mis en
 * avant (liseré bleu, « Disponible » s'il est téléchargé), puis ses autres
 * films, plus discrets.
 */
export function PersonSheet({ id, loadPerson }: { id: number; loadPerson: (id: number) => Promise<PersonFilmography> }) {
    const { data, isLoading, isError } = useQuery({
        queryKey: ["person", id],
        queryFn: () => loadPerson(id),
        staleTime: 3_600_000,
    });
    if (isLoading) {
        return <Loader2 className="mx-auto animate-spin text-slate-400" style={{ width: u(6), height: u(6), margin: `${u(6)} auto` }} />;
    }
    if (isError || !data?.person) {
        return (
            <p className="text-slate-400" style={{ fontSize: u(3) }}>
                {data?.error ?? "Filmographie indisponible pour le moment."}
            </p>
        );
    }
    const p = data.person;
    const facts = [p.birthday ? `Né(e) le ${new Date(p.birthday).toLocaleDateString("fr-FR")}` : "", p.place_of_birth ?? ""].filter(Boolean);
    return (
        <div className="flex flex-col" style={{ gap: u(3) }}>
            <div className="flex" style={{ gap: u(3) }}>
                {p.photo && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.photo} alt="" className="shrink-0 rounded-xl object-cover" style={{ width: u(18), height: u(24) }} />
                )}
                <div className="min-w-0">
                    {facts.length > 0 && (
                        <p className="text-slate-400" style={{ fontSize: u(2.8) }}>
                            {facts.join(" · ")}
                        </p>
                    )}
                    {p.biography && (
                        <p className="line-clamp-5 leading-relaxed text-slate-300" style={{ fontSize: u(2.9), marginTop: u(1) }}>
                            {p.biography}
                        </p>
                    )}
                </div>
            </div>

            {data.in_library.length > 0 && (
                <section>
                    <p className="font-medium uppercase text-[#8CC4FF]" style={{ fontSize: u(2.6), letterSpacing: "0.14em", marginBottom: u(1.6) }}>
                        Dans ta médiathèque · {data.in_library.length}
                    </p>
                    <ul className="grid grid-cols-6 portrait:grid-cols-4" style={{ gap: u(2) }}>
                        {data.in_library.map((movie) => (
                            <MoviePoster key={movie.tmdb_id} movie={movie} owned />
                        ))}
                    </ul>
                </section>
            )}

            {data.discover.length > 0 && (
                <section>
                    <p className="font-medium uppercase text-slate-500" style={{ fontSize: u(2.6), letterSpacing: "0.14em", marginBottom: u(1.6) }}>
                        Autres films
                    </p>
                    <ul className="grid grid-cols-8 portrait:grid-cols-5" style={{ gap: u(1.6) }}>
                        {data.discover.slice(0, 24).map((movie) => (
                            <MoviePoster key={movie.tmdb_id} movie={movie} />
                        ))}
                    </ul>
                </section>
            )}
        </div>
    );
}

function MoviePoster({ movie, owned = false }: { movie: PersonFilmography["discover"][number]; owned?: boolean }) {
    const ready = owned && movie.has_file;
    return (
        <li className={cn("flex flex-col", !owned && "opacity-55")} style={{ gap: u(0.6) }}>
            <div
                className={cn(
                    "relative aspect-[2/3] overflow-hidden bg-white/[0.06]",
                    owned && (ready ? "ring-2 ring-[#4A9EFF]" : "ring-1 ring-white/25"),
                )}
                style={{ borderRadius: u(1.2) }}
            >
                {movie.poster ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={movie.poster} alt="" loading="lazy" className="h-full w-full object-cover" />
                ) : (
                    <span className="flex h-full items-center justify-center p-1 text-center text-slate-500" style={{ fontSize: u(2.2) }}>
                        {movie.title}
                    </span>
                )}
                {owned && (
                    <span
                        className={cn("absolute inset-x-0 bottom-0 text-center font-semibold", ready ? "bg-[#4A9EFF] text-[#0b1220]" : "bg-black/70 text-slate-300")}
                        style={{ fontSize: u(2), padding: `${u(0.4)} 0` }}
                    >
                        {ready ? "Disponible" : "Pas encore téléchargé"}
                    </span>
                )}
            </div>
            <span className="truncate text-slate-200" style={{ fontSize: u(2.4) }}>
                {movie.title}
            </span>
            <span className="truncate text-slate-500" style={{ fontSize: u(2.1) }}>
                {[movie.year, movie.character].filter(Boolean).join(" · ")}
            </span>
        </li>
    );
}
