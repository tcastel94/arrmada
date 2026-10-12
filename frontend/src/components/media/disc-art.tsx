"use client";

/**
 * Disque Blu-ray / DVD d'un titre, et le vrai boîtier dont il sort (façon
 * Aeon Nox, le même rendu que la fiche de l'appli Kodi).
 * ----------------------------------------------------------------
 * - `DiscArt` : le rond imprimé du disque (fanart.tv, PNG transparent) ou, à
 *   défaut, un disque dessiné à partir de l'affiche : image recadrée en
 *   cercle, trou central percé par un masque CSS, anneau transparent du moyeu
 *   et micro-sillons. Le reflet de lumière reste FIXE pendant que le disque
 *   tourne (la lampe ne tourne pas avec lui) : c'est ce qui fait « vrai ».
 * - `DiscCase` : un vrai boîtier, l'affiche glissée dessous comme une jaquette.
 *   Les couches, de bas en haut (mêmes valeurs que la texture Kodi générée par
 *   kodi-addon/tools/make_textures.py) :
 *     1. plastique teinté (bleu Blu-ray, noir 4K / DVD, transparent sans fichier) ;
 *     2. bandeau du format (« Blu-ray Disc », « 4K ULTRA HD » + Blu-ray Disc) ;
 *     3. jaquette = l'affiche, recadrée au centre (un Blu-ray est plus large
 *        qu'une affiche) ;
 *     4. charnière à gauche (la jaquette s'enroule autour du dos), ombre
 *        intérieure du film qui la plaque, reflet du film en diagonale.
 *   Proportions : Blu-ray 392 × 530 (un vrai fait 135 × 171,5 mm, un poil plus
 *   large : on recadre moins l'affiche), DVD plus haut 392 × 552, sans bandeau.
 *
 * Accessibilité : décoratif (aria-hidden), sauf l'affiche et le bouton
 * sortir / ranger. « Réduire les animations » : le disque sort sans rotation.
 */
/* eslint-disable @next/next/no-img-element */
import { useState, type CSSProperties } from "react";
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

/* ─── Géométrie du boîtier (en px de la texture Kodi, convertis en %) ─── */
const CASE_W = 392;
const FRAME = 8; // plastique visible autour de la jaquette
const BANNER = 56; // bandeau du format
const HINGE = 30; // charnière, côté gauche

type CaseStyle = {
    /** Hauteur de la texture Kodi (le ratio du boîtier). */
    height: number;
    /** Plastique teinté du boîtier. */
    plastic: string;
    /** Bandeau du haut (dégradé), ou rien (DVD, sans fichier). */
    banner: string | null;
};

const CASE_STYLE: Record<CaseFormat, CaseStyle> = {
    bluray: { height: 530, plastic: "rgb(14 91 200 / 0.9)", banner: "linear-gradient(#2D84EA, #0A4AA2)" },
    uhd: { height: 530, plastic: "rgb(10 11 13 / 0.94)", banner: "linear-gradient(#2A2C31, #040405)" },
    dvd: { height: 552, plastic: "rgb(10 11 13 / 0.94)", banner: null },
    none: { height: 530, plastic: "rgb(201 211 226 / 0.22)", banner: null },
};

/** Charnière : jaquette assombrie vers le dos, arête claire, gorge et son reflet. */
const HINGE_BG = [
    "linear-gradient(90deg, transparent 54%, rgb(0 0 0 / 0.45) 62%, transparent 68%, rgb(255 255 255 / 0.28) 71%, transparent 75%, transparent 88%, rgb(0 0 0 / 0.18) 92%, transparent 95%, rgb(255 255 255 / 0.1) 98%, transparent)",
    "linear-gradient(90deg, transparent 2%, rgb(255 255 255 / 0.2) 8%, transparent 14%)",
    "linear-gradient(90deg, rgb(0 0 0 / 0.45), transparent)",
].join(", ");

/** Film transparent : grand reflet en diagonale à bord net, bande fine derrière, voile. */
const SLEEVE_BG = [
    "linear-gradient(135deg, rgb(255 255 255 / 0.13), rgb(255 255 255 / 0.08) 22%, transparent 24.5%, transparent 26.5%, rgb(255 255 255 / 0.06) 27.5%, rgb(255 255 255 / 0.06) 29.5%, transparent 30.5%)",
    "linear-gradient(rgb(255 255 255 / 0.035), rgb(255 255 255 / 0.035))",
].join(", ");

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
 * Le boîtier seul : plastique, bandeau, jaquette (affiche), charnière, film.
 * Prend toute la largeur de son parent ; la hauteur suit le format.
 */
export function BluRayCase({
    poster,
    format,
    title,
    className,
}: {
    poster?: string | null;
    format: CaseFormat;
    title: string;
    className?: string;
}) {
    const style = CASE_STYLE[format];
    const h = style.height;
    // Positions en % : horizontales sur la largeur, verticales sur la hauteur
    const frameX = `${(FRAME / CASE_W) * 100}%`;
    const frameY = `${(FRAME / h) * 100}%`;
    const sleeveH = h - 2 * FRAME; // hauteur du film (bandeau + jaquette)
    const bannerPct = style.banner ? (BANNER / sleeveH) * 100 : 0;
    const hingePct = (HINGE / (CASE_W - 2 * FRAME)) * 100;

    return (
        <div
            className={cn("relative", className)}
            style={{ aspectRatio: `${CASE_W} / ${h}`, containerType: "inline-size" } as CSSProperties}
        >
            {/* Ombre portée sous le boîtier */}
            <div aria-hidden className="absolute inset-x-[3%] bottom-[-2%] top-[3%] rounded-[14px] bg-black/75 blur-2xl" />

            {/* 1. Plastique teinté, arête claire */}
            <div
                aria-hidden
                className="absolute inset-0 rounded-[10px]"
                style={{
                    background: style.plastic,
                    boxShadow: "inset 0 0 0 1px rgb(255 255 255 / 0.28), inset 0 0 0 2px rgb(0 0 0 / 0.2)",
                }}
            />

            {/* Film transparent : bandeau + jaquette, puis charnière et reflets par-dessus */}
            <div
                className="absolute overflow-hidden rounded-[3px] shadow-[0_0_0_1px_rgb(0_0_0/0.35)]"
                style={{ left: frameX, right: frameX, top: frameY, bottom: frameY }}
            >
                {/* 2. Bandeau du format */}
                {style.banner && (
                    <div
                        aria-hidden
                        className="relative z-10 flex items-center font-bold text-white shadow-[0_3px_6px_rgb(0_0_0/0.45)]"
                        style={{
                            height: `${bannerPct}%`,
                            background: style.banner,
                            boxShadow:
                                format === "uhd"
                                    ? "inset 0 1px 0 rgb(255 255 255 / 0.18), inset 0 -2px 0 #B4BAC2, 0 3px 6px rgb(0 0 0 / 0.45)"
                                    : "inset 0 1px 0 rgb(255 255 255 / 0.4), inset 0 -2px 3px rgb(0 0 0 / 0.35), 0 3px 6px rgb(0 0 0 / 0.45)",
                        }}
                    >
                        {format === "uhd" ? (
                            <div className="flex w-full items-center justify-between px-[4.5%]">
                                <span className="tracking-wide" style={{ fontSize: "6.6cqw" }}>
                                    4K ULTRA HD
                                </span>
                                <span className="font-semibold opacity-90" style={{ fontSize: "3.4cqw" }}>
                                    Blu-ray Disc
                                </span>
                            </div>
                        ) : (
                            <span
                                className="w-full text-center [text-shadow:0_1px_2px_rgb(0_0_0/0.4)]"
                                style={{ fontSize: "6.6cqw" }}
                            >
                                Blu-ray Disc
                            </span>
                        )}
                    </div>
                )}

                {/* 3. Jaquette : l'affiche, recadrée au centre */}
                <div className="absolute inset-x-0 bottom-0 bg-muted/40" style={{ top: `${bannerPct}%` }}>
                    {poster && <img src={poster} alt={`Jaquette de ${title}`} className="h-full w-full object-cover" />}
                </div>

                {/* 4. Charnière (côté gauche, sur toute la hauteur du film) */}
                <div
                    aria-hidden
                    className="pointer-events-none absolute inset-y-0 left-0 z-20"
                    style={{ width: `${hingePct}%`, background: HINGE_BG }}
                />
                {/* Ombre intérieure du film qui plaque la jaquette */}
                <div aria-hidden className="pointer-events-none absolute inset-0 z-20 shadow-[inset_0_0_10px_rgb(0_0_0/0.5)]" />
                {/* Reflet du film en diagonale + arêtes claires (haut, droite) */}
                <div
                    aria-hidden
                    className="pointer-events-none absolute inset-0 z-20"
                    style={{
                        background: SLEEVE_BG,
                        boxShadow: "inset 0 1px 0 rgb(255 255 255 / 0.32), inset -1px 0 0 rgb(255 255 255 / 0.14)",
                    }}
                />
            </div>
        </div>
    );
}

/**
 * Boîtier + disque qui en sort. Le disque sort vers la droite au montage
 * (≈ 60 % de sa largeur), tourne, et le bouton permet de le ranger / le
 * ressortir.
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

                <BluRayCase poster={poster} format={format} title={title} />
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
