"use client";

/**
 * Miniature d'affiche pour les vues liste (médiathèque, manquants, suivi).
 * Repli sur une icône Film/Série si l'image est absente ou cassée.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { Film, Tv } from "lucide-react";
import { cn } from "@/lib/utils";

export function MediaThumb({
    src,
    alt,
    type,
    className,
}: {
    src?: string | null;
    alt: string;
    type?: string;
    /** Taille : par défaut 44×64 px. */
    className?: string;
}) {
    const [failed, setFailed] = useState(false);
    const Icon = type === "series" ? Tv : Film;
    return (
        <div
            className={cn(
                "relative shrink-0 overflow-hidden rounded-lg bg-muted/40 ring-1 ring-white/[0.08]",
                className ?? "h-16 w-11",
            )}
        >
            {src && !failed ? (
                <img
                    src={src}
                    alt={alt}
                    loading="lazy"
                    onError={() => setFailed(true)}
                    className="h-full w-full object-cover transition-transform duration-500 ease-smooth group-hover:scale-110"
                />
            ) : (
                <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-muted/60 to-primary/10">
                    <Icon className="h-4 w-4 text-muted-foreground/40" strokeWidth={1.6} />
                </div>
            )}
        </div>
    );
}
