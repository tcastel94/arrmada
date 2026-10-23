"use client";

/**
 * Vrai dès que la page a défilé de plus de `threshold` pixels.
 * ----------------------------------------------------------------
 * Sert à la barre du haut iOS : transparente tant qu'on est en haut de
 * page, elle prend son fond flouté et affiche le petit titre une fois le
 * grand titre sorti de l'écran.
 * L'écouteur est « passif » (il ne bloque jamais le défilement) et ne
 * déclenche un rendu React que lorsque l'état bascule, pas à chaque pixel.
 */
import { useEffect, useState } from "react";

export function useScrolled(threshold = 8): boolean {
    const [scrolled, setScrolled] = useState(false);

    useEffect(() => {
        let frame = 0;
        const update = () => {
            frame = 0;
            setScrolled(window.scrollY > threshold);
        };
        const onScroll = () => {
            if (!frame) frame = requestAnimationFrame(update);
        };
        update();
        window.addEventListener("scroll", onScroll, { passive: true });
        return () => {
            window.removeEventListener("scroll", onScroll);
            if (frame) cancelAnimationFrame(frame);
        };
    }, [threshold]);

    return scrolled;
}
