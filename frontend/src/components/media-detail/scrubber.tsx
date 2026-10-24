"use client";

/**
 * Curseur accessible (role="slider") pour la position de lecture et le volume.
 * ----------------------------------------------------------------
 * Pourquoi un composant maison plutôt qu'une <div onClick> :
 *  - utilisable au clavier (← → ±step, PgPréc/PgSuiv ±bigStep, Début/Fin) ;
 *  - lu correctement par les lecteurs d'écran (aria-valuenow / valuetext) ;
 *  - glisser-déposer à la souris ET au doigt (pointer events + capture) ;
 *  - pas de « saut » : pendant le glisser on affiche la valeur locale, et
 *    après validation on la garde jusqu'à ce que le serveur la confirme
 *    (sinon le curseur revient à l'ancienne valeur le temps d'un polling).
 */
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { cn } from "@/lib/utils";

interface ScrubberProps {
    /** Valeur serveur, 0 → 100. */
    value: number;
    /** Appelé en continu pendant le glisser (ex : volume debouncé). */
    onChange?: (v: number) => void;
    /** Valeur validée (relâchement du pointeur ou clavier après une courte pause). */
    onCommit: (v: number) => void;
    /** Nom accessible (obligatoire : « Position de lecture », « Volume »…). */
    label: string;
    /** Texte lu par le lecteur d'écran (« 12:03 sur 1:45:00 »). */
    valueText?: (v: number) => string;
    step?: number;
    bigStep?: number;
    tone?: "violet" | "primary";
    size?: "sm" | "md";
    disabled?: boolean;
    className?: string;
}

const clamp = (v: number) => Math.max(0, Math.min(100, v));

export function Scrubber({
    value,
    onChange,
    onCommit,
    label,
    valueText,
    step = 1,
    bigStep = 10,
    tone = "violet",
    size = "md",
    disabled,
    className,
}: ScrubberProps) {
    const trackRef = useRef<HTMLDivElement>(null);
    const [drag, setDrag] = useState<number | null>(null);
    // Valeur affichée en attendant le serveur. `sent` = déjà envoyée (sinon
    // c'est une saisie clavier encore dans le délai de regroupement).
    const [pending, setPending] = useState<{ v: number; sent: boolean } | null>(null);
    const keyTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const pendingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Dès que le serveur rejoint la valeur envoyée (±3), on relâche l'override.
    useEffect(() => {
        if (pending?.sent && Math.abs(value - pending.v) <= 3) setPending(null);
    }, [value, pending]);

    useEffect(
        () => () => {
            if (keyTimer.current) clearTimeout(keyTimer.current);
            if (pendingTimer.current) clearTimeout(pendingTimer.current);
        },
        [],
    );

    const shown = clamp(drag ?? pending?.v ?? value);

    /** Mémorise la valeur envoyée ; filet de sécurité de 3 s si le serveur ne bouge pas. */
    const commit = (v: number) => {
        setPending({ v, sent: true });
        if (pendingTimer.current) clearTimeout(pendingTimer.current);
        pendingTimer.current = setTimeout(() => setPending(null), 3000);
        onCommit(v);
    };

    const fromPointer = (clientX: number) => {
        const rect = trackRef.current?.getBoundingClientRect();
        if (!rect || rect.width === 0) return shown;
        return clamp(((clientX - rect.left) / rect.width) * 100);
    };

    const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
        if (disabled) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        const v = fromPointer(e.clientX);
        setDrag(v);
        onChange?.(v);
    };
    const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
        if (drag === null) return;
        const v = fromPointer(e.clientX);
        setDrag(v);
        onChange?.(v);
    };
    const onPointerUp = (e: PointerEvent<HTMLDivElement>) => {
        if (drag === null) return;
        const v = fromPointer(e.clientX);
        setDrag(null);
        commit(Math.round(v));
    };

    const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
        if (disabled) return;
        let next: number | null = null;
        const base = drag ?? pending?.v ?? value;
        switch (e.key) {
            case "ArrowRight":
            case "ArrowUp":
                next = base + step;
                break;
            case "ArrowLeft":
            case "ArrowDown":
                next = base - step;
                break;
            case "PageUp":
                next = base + bigStep;
                break;
            case "PageDown":
                next = base - bigStep;
                break;
            case "Home":
                next = 0;
                break;
            case "End":
                next = 100;
                break;
        }
        if (next === null) return;
        e.preventDefault();
        const v = Math.round(clamp(next));
        // Affichage immédiat, envoi groupé après 350 ms sans touche (pas de rafale de requêtes).
        setPending({ v, sent: false });
        if (keyTimer.current) clearTimeout(keyTimer.current);
        keyTimer.current = setTimeout(() => commit(v), 350);
    };

    // Barre pleine : blanche pour la lecture vidéo (comme le lecteur iOS),
    // bleue pour les autres réglages.
    const fill = tone === "violet" ? "bg-white" : "bg-primary";

    return (
        <div
            role="slider"
            tabIndex={disabled ? -1 : 0}
            aria-label={label}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(shown)}
            aria-valuetext={valueText ? valueText(shown) : `${Math.round(shown)} %`}
            aria-disabled={disabled || undefined}
            onKeyDown={onKeyDown}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={() => setDrag(null)}
            className={cn(
                "group relative flex cursor-pointer touch-none select-none items-center py-2 outline-none",
                "focus-visible:rounded-full focus-visible:ring-2 focus-visible:ring-ring/70",
                disabled && "cursor-not-allowed opacity-50",
                className,
            )}
        >
            <div
                ref={trackRef}
                className={cn(
                    "relative w-full overflow-visible rounded-full bg-white/[0.18] transition-[height] duration-200",
                    size === "sm" ? "h-1" : "h-1.5 group-hover:h-2",
                    drag !== null && "h-2",
                )}
            >
                <div
                    className={cn(
                        "absolute inset-y-0 left-0 rounded-full",
                        fill,
                        // Pas de transition pendant le glisser (suivi direct du doigt).
                        drag === null && "transition-[width] duration-500 ease-smooth",
                    )}
                    style={{ width: `${shown}%` }}
                />
                {/* Poignée : visible au survol, au focus et pendant le glisser */}
                <div
                    className={cn(
                        "absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white transition-[opacity,transform] duration-200",
                        drag !== null ? "scale-110 opacity-100" : "scale-75 opacity-0 group-hover:scale-100 group-hover:opacity-100 group-focus-visible:scale-100 group-focus-visible:opacity-100",
                        drag === null && "transition-[left,opacity,transform]",
                    )}
                    style={{ left: `${shown}%` }}
                />
            </div>
        </div>
    );
}
