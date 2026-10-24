"use client";

/**
 * Le vrai boîtier Blu-ray / 4K / DVD d'un titre, qui s'ouvre, et son disque
 * (façon Aeon Nox, le même rendu que la fiche de l'appli Kodi).
 * ----------------------------------------------------------------
 * - `DiscArt` : le rond imprimé du disque (fanart.tv ou disc.png du dossier,
 *   PNG transparent) ou, à défaut, un disque dessiné à partir de l'affiche :
 *   image recadrée en cercle, trou central percé par un masque CSS, anneau
 *   transparent du moyeu et micro-sillons. Le reflet de lumière reste FIXE
 *   pendant que le disque tourne (la lampe ne tourne pas avec lui).
 * - `BluRayCase` : la façade du boîtier, l'affiche glissée dessous comme une
 *   jaquette. Couches, de bas en haut (mêmes valeurs que la texture Kodi de
 *   kodi-addon/tools/make_textures.py) : plastique teinté, bandeau du format,
 *   jaquette recadrée au centre, charnière à gauche, film transparent.
 * - `CaseTray` : l'intérieur du boîtier ouvert (plateau, picots du moyeu).
 * - `OpeningCase` : le tout en 3D. À l'ouverture de la fiche, la façade
 *   pivote sur sa charnière (comme une porte qui s'entrouvre vers toi), le
 *   disque arrive en roulant et se pose sur le moyeu, puis le boîtier se
 *   referme. Un clic l'ouvre / le referme (disque qui tourne dedans).
 *
 * Proportions : Blu-ray 392 × 530 (un vrai fait 135 × 171,5 mm, un poil plus
 * large : on recadre moins l'affiche), DVD plus haut 392 × 552, sans bandeau.
 * Accessibilité : décoratif sauf le bouton ouvrir / fermer ; « Réduire les
 * animations » : pas d'introduction, ouverture instantanée, disque immobile.
 */
/* eslint-disable @next/next/no-img-element */
import { useEffect, useState, type CSSProperties } from "react";
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
    /** Plastique teinté du boîtier (façade). */
    plastic: string;
    /** Plastique de l'intérieur (plateau), plus opaque. */
    tray: string;
    /** Bandeau du haut (dégradé), ou rien (DVD, sans fichier). */
    banner: string | null;
};

const CASE_STYLE: Record<CaseFormat, CaseStyle> = {
    bluray: {
        height: 530,
        plastic: "rgb(14 91 200 / 0.9)",
        tray: "linear-gradient(160deg, #1663CF, #0B3F8F)",
        banner: "linear-gradient(#2D84EA, #0A4AA2)",
    },
    uhd: {
        height: 530,
        plastic: "rgb(10 11 13 / 0.94)",
        tray: "linear-gradient(160deg, #1D1F24, #07080A)",
        banner: "linear-gradient(#2A2C31, #040405)",
    },
    dvd: {
        height: 552,
        plastic: "rgb(10 11 13 / 0.94)",
        tray: "linear-gradient(160deg, #1D1F24, #07080A)",
        banner: null,
    },
    none: {
        height: 530,
        plastic: "rgb(201 211 226 / 0.22)",
        tray: "linear-gradient(160deg, rgb(201 211 226 / 0.25), rgb(120 130 150 / 0.2))",
        banner: null,
    },
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

/** Diamètre du disque / largeur du boîtier (120 mm pour 135 mm). */
const DISC_RATIO = 0.88;

export function DiscArt({
    discart,
    fallback,
    spinning = false,
    className,
}: {
    /** Rond imprimé (fanart.tv ou disc.png du dossier : déjà circulaire, fond transparent). */
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
            {/* Sens inverse des aiguilles d'une montre : un disque vu côté
                étiquette, et le même sens que quand il roule vers la gauche */}
            <motion.div
                className="absolute inset-0"
                animate={spinning && !reduce ? { rotate: -360 } : { rotate: 0 }}
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
 * La façade du boîtier : plastique, bandeau, jaquette (affiche), charnière, film.
 * Prend toute la largeur de son parent ; la hauteur suit le format.
 */
export function BluRayCase({
    poster,
    format,
    title,
    shadow = true,
    className,
}: {
    poster?: string | null;
    format: CaseFormat;
    title: string;
    /** Ombre portée sous le boîtier (désactivée quand la façade pivote en 3D). */
    shadow?: boolean;
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
            {shadow && (
                <div aria-hidden className="absolute inset-x-[3%] bottom-[-2%] top-[3%] rounded-[14px] bg-black/75 blur-2xl" />
            )}

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
                className="absolute overflow-hidden rounded-[3px]"
                style={{ left: frameX, right: frameX, top: frameY, bottom: frameY }}
            >
                {/* 2. Bandeau du format */}
                {style.banner && (
                    <div
                        aria-hidden
                        className="relative z-10 flex items-center font-bold text-white"
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
                <div aria-hidden className="pointer-events-none absolute inset-0 z-20" />
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
 * L'intérieur du boîtier (visible quand la façade s'ouvre) : plateau moulé,
 * picots du moyeu qui tiennent le disque, logo en relief en bas.
 */
export function CaseTray({ format, className }: { format: CaseFormat; className?: string }) {
    const style = CASE_STYLE[format];
    return (
        <div
            aria-hidden
            className={cn("relative overflow-hidden rounded-[10px]", className)}
            style={{
                aspectRatio: `${CASE_W} / ${style.height}`,
                background: style.tray,
                boxShadow: "inset 0 0 0 1px rgb(255 255 255 / 0.2), inset 0 0 24px rgb(0 0 0 / 0.55)",
                containerType: "inline-size",
            } as CSSProperties}
        >
            {/* Plateau moulé (léger creux) */}
            <div className="absolute inset-[4%] rounded-[8px] bg-black/25 shadow-[inset_0_2px_10px_rgb(0_0_0/0.6)]" />
            {/* Logement du disque */}
            <div
                className="absolute left-1/2 top-1/2 aspect-square -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{
                    width: `${DISC_RATIO * 100 + 2}%`,
                    background: "radial-gradient(circle, transparent 66%, rgb(0 0 0 / 0.35) 70%, transparent 71%)",
                    boxShadow: "inset 0 0 18px rgb(0 0 0 / 0.5)",
                }}
            />
            {/* Picots du moyeu (couronne crantée) + bouton central */}
            <div
                className="absolute left-1/2 top-1/2 aspect-square w-[30%] -translate-x-1/2 -translate-y-1/2 rounded-full"
                style={{
                    background:
                        "repeating-conic-gradient(rgb(255 255 255 / 0.32) 0 9deg, rgb(0 0 0 / 0.25) 9deg 22.5deg)",
                    maskImage: "radial-gradient(circle, transparent 0 48%, #000 50% 70%, transparent 72%)",
                    WebkitMaskImage: "radial-gradient(circle, transparent 0 48%, #000 50% 70%, transparent 72%)",
                }}
            />
            <div className="absolute left-1/2 top-1/2 aspect-square w-[12%] -translate-x-1/2 -translate-y-1/2 rounded-full bg-gradient-to-br from-white/40 to-black/40 ring-1 ring-white/30" />
            {/* Logo en relief, en bas du plateau */}
            {format !== "none" && (
                <span
                    className="absolute inset-x-0 bottom-[6%] text-center font-bold text-white/25 [text-shadow:0_-1px_0_rgb(0_0_0/0.4)]"
                    style={{ fontSize: "4.2cqw" }}
                >
                    {format === "dvd" ? "DVD" : "Blu-ray Disc"}
                </span>
            )}
        </div>
    );
}

/**
 * Boîtier en 3D qui s'ouvre, avec le disque qui rentre dedans en roulant.
 *
 * Déroulé à l'arrivée sur la fiche (≈ 2,6 s) : la façade s'entrouvre sur sa
 * charnière, le disque arrive de la droite en roulant (sa rotation suit la
 * distance parcourue, comme une vraie roue), se pose sur le moyeu, puis le
 * boîtier se referme. Ensuite, un clic ouvre / referme ; ouvert, le disque
 * tourne dans son plateau.
 *
 * Analogie : trois calques empilés (plateau, disque, façade) ; seule la
 * façade tourne autour de son bord gauche, comme une porte sur ses gonds.
 */
export function OpeningCase({
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
    const [open, setOpen] = useState(false);
    // Disque dans son plateau ? (faux au début : il arrive pendant l'introduction)
    const [discIn, setDiscIn] = useState(!!reduce);
    const [busy, setBusy] = useState(!reduce);

    useEffect(() => {
        if (reduce) {
            setDiscIn(true);
            setBusy(false);
            return;
        }
        const timers = [
            window.setTimeout(() => setOpen(true), 350), // la façade s'entrouvre
            window.setTimeout(() => setDiscIn(true), 850), // le disque arrive en roulant
            window.setTimeout(() => setOpen(false), 2350), // le boîtier se referme
            window.setTimeout(() => setBusy(false), 3000),
        ];
        return () => timers.forEach(window.clearTimeout);
    }, [reduce]);

    // Rouler sans glisser : angle (rad) = distance / rayon. Le disque part à
    // 75 % de son diamètre à droite → 0,75 D / 0,5 D = 1,5 rad ≈ 86°.
    const ROLL_FROM = 0.75;
    const ROLL_DEG = Math.round(((ROLL_FROM * 2) * 180) / Math.PI);

    return (
        <div className={cn("relative", className)}>
            <button
                type="button"
                onClick={() => !busy && setOpen((v) => !v)}
                aria-pressed={open}
                aria-label={open ? `Fermer le boîtier de ${title}` : `Ouvrir le boîtier de ${title}`}
                className="group relative block w-full rounded-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                style={{ perspective: 1300, perspectiveOrigin: "50% 45%" }}
            >
                {/* Ombre portée (immobile, sous les trois calques) */}
                <div aria-hidden className="absolute inset-x-[3%] bottom-[-2%] top-[3%] rounded-[14px] bg-black/75 blur-2xl" />

                <div className="relative" style={{ transformStyle: "preserve-3d" }}>
                    {/* 1. Intérieur du boîtier (légèrement en retrait : jamais devant la façade) */}
                    <div style={{ transform: "translateZ(-2px)" }}>
                        <CaseTray format={format} className="w-full" />
                    </div>

                    {/* 2. Disque, posé sur le moyeu (ou en route vers lui) */}
                    <motion.div
                        className="absolute top-1/2"
                        style={{ left: `${((1 - DISC_RATIO) / 2) * 100}%`, width: `${DISC_RATIO * 100}%`, y: "-50%", z: -1 }}
                        initial={false}
                        animate={
                            discIn
                                ? { x: "0%", rotate: 0, opacity: 1 }
                                : { x: `${ROLL_FROM * 100}%`, rotate: ROLL_DEG, opacity: 0 }
                        }
                        transition={
                            reduce
                                ? { duration: 0 }
                                : {
                                      x: { duration: 1.15, ease: [0.22, 1, 0.36, 1] },
                                      rotate: { duration: 1.15, ease: [0.22, 1, 0.36, 1] },
                                      opacity: { duration: 0.35 },
                                  }
                        }
                    >
                        <DiscArt discart={discart} fallback={poster} spinning={open && discIn && !busy} className="w-full" />
                    </motion.div>

                    {/* 3. Façade : pivote sur sa charnière (bord gauche), vers toi */}
                    <motion.div
                        className="absolute inset-0"
                        style={{ transformOrigin: "left center", transformStyle: "preserve-3d", backfaceVisibility: "hidden" }}
                        initial={false}
                        animate={{ rotateY: open ? -76 : 0 }}
                        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 60, damping: 14 }}
                    >
                        <BluRayCase poster={poster} format={format} title={title} shadow={false} />
                    </motion.div>
                </div>
            </button>
            <p className="mt-3 text-center text-[11px] font-medium text-muted-foreground">
                {open ? "Clique pour refermer le boîtier" : "Clique sur le boîtier pour l'ouvrir"}
            </p>
        </div>
    );
}
