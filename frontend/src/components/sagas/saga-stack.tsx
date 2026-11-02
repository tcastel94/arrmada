"use client";

/**
 * Pile de trois affiches d'une saga, qui s'ouvre en éventail au survol ou
 * au focus du lien parent (classe `group`), comme sur la TV.
 */
/* eslint-disable @next/next/no-img-element */
import { Film } from "lucide-react";
import { cn } from "@/lib/utils";

/** Couleur du badge d'une saga (voir sagaBadge). */
export const SAGA_TONE: Record<string, string> = {
    ok: "bg-success/15 text-success",
    missing: "bg-primary/15 text-primary",
    wanted: "bg-primary/15 text-primary",
    soon: "bg-warning/15 text-warning",
};

const PLACE = [
    // Gauche, centre, droite : fermé → ouvert (au survol du parent)
    "-rotate-[4deg] -translate-x-[8%] group-hover:-rotate-[12deg] group-hover:-translate-x-[32%] group-hover:translate-y-[5%] group-focus-visible:-rotate-[12deg] group-focus-visible:-translate-x-[32%]",
    "z-10 group-hover:-translate-y-[3%] group-focus-visible:-translate-y-[3%]",
    "rotate-[4deg] translate-x-[8%] group-hover:rotate-[12deg] group-hover:translate-x-[32%] group-hover:translate-y-[5%] group-focus-visible:rotate-[12deg] group-focus-visible:translate-x-[32%]",
];

export function SagaStack({ posters, title, className }: { posters: string[]; title: string; className?: string }) {
    // Toujours trois places : une saga de deux films répète la première affiche derrière
    const three = posters.length >= 3 ? posters.slice(0, 3) : [posters[1] ?? posters[0], posters[0], posters[1] ?? posters[0]];
    return (
        <div className={cn("relative aspect-[1/1.05] w-full", className)}>
            {three.map((src, i) => (
                <div
                    key={i}
                    className={cn(
                        "absolute left-[20%] top-[4%] aspect-[2/3] w-[60%] overflow-hidden rounded-[10px] bg-white/[0.06] shadow-[0_10px_28px_-12px_rgba(0,0,0,0.9)]",
                        "transition-transform duration-300 ease-out motion-reduce:transition-none",
                        PLACE[i],
                    )}
                >
                    {src ? (
                        <img src={src} alt={i === 1 ? title : ""} loading="lazy" className="h-full w-full object-cover" />
                    ) : (
                        <Film className="m-auto mt-[40%] h-8 w-8 text-white/20" />
                    )}
                </div>
            ))}
        </div>
    );
}
