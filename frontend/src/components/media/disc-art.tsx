"use client";

/**
 * Disque Blu-ray / DVD d'un titre, et le boîtier dont il sort.
 * ----------------------------------------------------------------
 * - `DiscArt` : le rond imprimé du disque (fanart.tv, PNG transparent) ou, à
 *   défaut, un disque dessiné à partir de l'affiche : image recadrée en
 *   cercle, trou central percé par un masque CSS, anneau transparent du moyeu
 *   et micro-sillons. Le reflet de lumière reste FIXE pendant que le disque
 *   tourne (la lampe ne tourne pas avec lui) : c'est ce qui fait « vrai ».
 * - `DiscCase` : boîtier (affiche + bandeau BLU-RAY / 4K ULTRA HD / DVD) et
 *   disque qui en sort au montage, tourne, et rentre / ressort au clic.
 *
 * Accessibilité : décoratif (aria-hidden), sauf le bouton sortir / ranger.
 * « Réduire les animations » : le disque sort sans rotation.
 */
/* eslint-disable @next/next/no-img-element */
import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";

/** Format du boîtier d'après la résolution du fichier (2160 → 4K, SD → DVD). */
export type CaseFormat = "uhd" | "bluray" | "dvd" | "none";

export function caseFormat(resolution: number | string | null | undefined, hasFile = true): CaseFormat {
    if (!hasFile) return "none";
    const n = typeof resolution === "number" ? resolution : parseInt(String(resolution ?? ""), 10);
    if (!n || Number.isNaN(n)) return "bluray";
    if (n >= 2000) return "uhd";
    if (n >= 700) return "bluray";
    return "dvd";
}

const CASE_STYLE: Record<CaseFormat, { band: string; label: string; plastic: string }> = {
    uhd: { band: "bg-black text-white", label: "4K ULTRA HD", plastic: "ring-black/80 bg-neutral-950" },
    bluray: { band: "bg-[#0A5FC4] text-white", label: "BLU-RAY", plastic: "ring-[#0A5FC4]/70 bg-[#0B2E5C]" },
    dvd: { band: "bg-neutral-800 text-white", label: "DVD", plastic: "ring-neutral-700 bg-neutral-900" },
    none: { band: "", label: "", plastic: "ring-white/15 bg-neutral-900" },
};

/** Masque : disque plein, trou central transparent (≈ 15 mm sur 120 mm). */
const HOLE_MASK = "radial-gradient(circle at center, transparent 0 7.5%, #000 8%)";

export function DiscArt({
    discart,
    fallback,
    spinning = false,
    className,
}: {
    /** Rond imprimé fanart.tv (déjà circulaire, fond transparent). */
    discart?: string | null;
    /** Affiche / fond utilisé pour dessiner le disque s'il n'y a pas de rond imprimé. */
    fallback?: string | null;
    spinning?: boolean;
    className?: string;
}) {
    const reduce = useReducedMotion();
    const [failed, setFailed] = useState(false);
    const useDisc = !!discart && !failed;

    return (
        <div aria-hidden className={cn("relative aspect-square", className)}>
            {/* Ombre portée (immobile) */}
            <div className="absolute inset-[3%] translate-y-[3%] rounded-full bg-black/60 blur-xl" />
            <motion.div
                className="absolute inset-0"
                animate={spinning && !reduce ? { rotate: 360 } : { rotate: 0 }}
                transition={spinning && !reduce ? { duration: 14, repeat: Infinity, ease: "linear" } : { duration: 0.6 }}
            >
                {useDisc ? (
                    <img
                        src={discart!}
                        alt=""
                        onError={() => setFailed(true)}
                        className="h-full w-full rounded-full object-contain"
                        style={{ maskImage: HOLE_MASK, WebkitMaskImage: HOLE_MASK }}
                    />
                ) : (
                    <div
                        className="relative h-full w-full overflow-hidden rounded-full bg-gradient-to-br from-slate-300 via-slate-500 to-slate-800"
                        style={{ maskImage: HOLE_MASK, WebkitMaskImage: HOLE_MASK }}
                    >
                        {fallback && <img src={fallback} alt="" className="h-full w-full object-cover opacity-90" />}
                        {/* Micro-sillons + anneau transparent du moyeu */}
                        <div
                            className="absolute inset-0"
                            style={{
                                background:
                                    "repeating-radial-gradient(circle at center, rgb(255 255 255 / 0.05) 0 1px, transparent 1px 3px)",
                            }}
                        />
                        <div
                            className="absolute inset-0"
                            style={{
                                background:
                                    "radial-gradient(circle at center, transparent 0 7.5%, rgb(220 228 240 / 0.85) 8% 9%, rgb(190 200 215 / 0.45) 9% 17%, rgb(0 0 0 / 0.35) 17% 18%, transparent 18.5%)",
                            }}
                        />
                    </div>
                )}
            </motion.div>
            {/* Reflet de lumière : ne tourne PAS avec le disque */}
            <div
                className="pointer-events-none absolute inset-0 rounded-full mix-blend-screen"
                style={{
                    background:
                        "conic-gradient(from 200deg at 50% 50%, transparent 0deg, rgb(255 255 255 / 0.22) 30deg, transparent 70deg, transparent 180deg, rgb(255 255 255 / 0.14) 215deg, transparent 255deg)",
                    maskImage: HOLE_MASK,
                    WebkitMaskImage: HOLE_MASK,
                }}
            />
            {/* Tranche du disque */}
            <div className="pointer-events-none absolute inset-0 rounded-full ring-1 ring-inset ring-white/25" />
        </div>
    );
}

/**
 * Boîtier + disque qui en sort. `poster` remplit le boîtier ; le disque sort
 * vers la droite au montage (≈ 60 % de sa largeur), tourne, et le bouton
 * permet de le ranger / le ressortir.
 */
export function DiscCase({
    poster,
    discart,
    format,
    title,
    className,
}: {
    poster?: string | null;
    discart?: string | null;
    format: CaseFormat;
    title: string;
    className?: string;
}) {
    const reduce = useReducedMotion();
    const [out, setOut] = useState(true);
    const style = CASE_STYLE[format];

    return (
        <div className={cn("relative", className)}>
            {/* Le boîtier prend 64 % de la largeur : le reste accueille le disque sorti */}
            <div className="relative mr-[36%]">
                {/* Disque : derrière le boîtier, glisse vers la droite. Diamètre
                    = 88 % de la largeur du boîtier (120 mm pour 135 mm en vrai). */}
                <motion.div
                    className="absolute left-[6%] top-1/2 w-[88%]"
                    style={{ y: "-50%" }}
                    initial={{ x: "0%" }}
                    animate={{ x: out ? "62%" : "0%" }}
                    transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 70, damping: 16, delay: out ? 0.35 : 0 }}
                >
                    <DiscArt discart={discart} fallback={poster} spinning={out} className="w-full" />
                </motion.div>

                {/* Boîtier : plastique coloré, bandeau du format, affiche */}
                <div
                    className={cn(
                        "relative aspect-[2/3] overflow-hidden rounded-[10px] p-[3.5%] shadow-[0_30px_70px_-20px_rgb(0_0_0/0.9)] ring-2",
                        style.plastic,
                    )}
                >
                    <div className="relative h-full w-full overflow-hidden rounded-[5px] bg-muted/40">
                        {poster && <img src={poster} alt={`Affiche de ${title}`} className="h-full w-full object-cover" />}
                        {format !== "none" && (
                            <div
                                className={cn(
                                    "absolute inset-x-0 top-0 flex h-[7%] items-center justify-center text-[clamp(8px,1.6vw,13px)] font-black tracking-[0.25em]",
                                    style.band,
                                )}
                            >
                                {style.label}
                            </div>
                        )}
                        {/* Reflet du film plastique */}
                        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/15 via-transparent to-transparent" />
                    </div>
                </div>
            </div>

            <button
                type="button"
                onClick={() => setOut((v) => !v)}
                className="mt-3 text-xs font-medium text-primary hover:underline"
            >
                {out ? "Ranger le disque" : "Sortir le disque"}
            </button>
        </div>
    );
}
