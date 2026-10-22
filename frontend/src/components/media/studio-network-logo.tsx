"use client";

/**
 * Studio (films) ou chaîne / plateforme (séries) sous forme de petit
 * « logo typographique » aux couleurs de la marque.
 * ----------------------------------------------------------------
 * Pas d'image externe ici : uniquement du texte stylé. Rien ne peut donc
 * « casser » la mise en page si un CDN de logos ne répond pas, et le
 * libellé reste lisible par un lecteur d'écran.
 *
 * Variantes :
 *  - "mini" : pastille discrète sous le titre d'une affiche (médiathèque),
 *             tronquée si le nom est long (nom complet en infobulle) ;
 *  - "hero" : pastille verre avec icône sur la fiche média.
 *
 * Les marques connues ont un libellé normalisé (« NETFLIX », « Apple TV+ »)
 * et leur couleur ; les autres gardent leur nom d'origine en neutre.
 */
import { Building2, Tv } from "lucide-react";
import { cn } from "@/lib/utils";

interface Brand {
    /** Motif testé sur le nom en minuscules. */
    test: RegExp;
    /** Libellé normalisé ; absent = on garde le nom d'origine. */
    label?: string;
    /** Couleur du texte + liseré (pastille). */
    tone: string;
    /** Typographie propre à la marque (capitales espacées, italique…). */
    font?: string;
}

/*
 * L'ordre compte : les motifs précis (« disney+ ») passent avant les
 * génériques (« disney »), sinon « Walt Disney Pictures » (studio de
 * cinéma) s'afficherait « Disney+ » (plateforme).
 */
const BRANDS: Brand[] = [
    { test: /netflix/, label: "NETFLIX", tone: "text-destructive ring-destructive/40 border-destructive/35", font: "font-black tracking-[0.16em]" },
    { test: /\bhbo max\b|^max$/, label: "Max", tone: "text-indigo-200 ring-indigo-400/40 border-indigo-400/35", font: "font-bold" },
    { test: /\bhbo\b/, label: "HBO", tone: "text-primary ring-primary/40 border-primary/35", font: "font-black tracking-[0.14em]" },
    { test: /disney\s?(\+|plus)/, label: "Disney+", tone: "text-sky-200 ring-primary/40 border-sky-400/35", font: "font-bold italic" },
    { test: /disney/, tone: "text-sky-200 ring-primary/35 border-sky-400/30", font: "font-semibold" },
    { test: /apple\s?tv/, label: "Apple TV+", tone: "text-zinc-100 ring-zinc-300/35 border-zinc-300/30", font: "font-semibold" },
    { test: /prime video|amazon prime|^amazon$/, label: "Prime Video", tone: "text-primary ring-primary/40 border-sky-500/35", font: "font-bold" },
    { test: /amazon/, tone: "text-primary ring-primary/35 border-sky-500/30", font: "font-semibold" },
    // « StudioCanal » n'est pas Canal+ : on exige « canal » en début de mot.
    { test: /\bcanal\s?(\+|plus)/, label: "CANAL+", tone: "text-white ring-white/40 border-white/30", font: "font-extrabold tracking-[0.14em]" },
    { test: /studio\s?canal/, tone: "text-white ring-white/30 border-white/25", font: "font-bold" },
    { test: /\bhulu\b/, label: "hulu", tone: "text-success ring-success/40 border-success/35", font: "font-bold lowercase" },
    { test: /paramount\s?(\+|plus)/, label: "Paramount+", tone: "text-blue-200 ring-blue-400/40 border-blue-400/35", font: "font-bold" },
    { test: /paramount/, tone: "text-blue-200 ring-blue-400/35 border-blue-400/30", font: "font-semibold" },
    { test: /peacock/, label: "Peacock", tone: "text-warning ring-warning/35 border-warning/30", font: "font-semibold" },
    { test: /\bbbc\b/, tone: "text-white ring-destructive/40 border-destructive/35", font: "font-bold tracking-wider" },
    { test: /warner/, tone: "text-warning ring-blue-400/40 border-blue-400/35", font: "font-bold" },
    { test: /marvel/, tone: "text-destructive ring-destructive/45 border-destructive/40", font: "font-extrabold uppercase tracking-wider" },
    { test: /pixar/, label: "PIXAR", tone: "text-sky-100 ring-primary/40 border-sky-400/35", font: "font-bold tracking-[0.16em]" },
    { test: /20th century|twentieth century/, tone: "text-warning ring-warning/35 border-warning/30", font: "font-semibold" },
    { test: /universal/, tone: "text-indigo-200 ring-indigo-400/40 border-indigo-400/35", font: "font-bold uppercase tracking-wider" },
    { test: /\bsony\b|columbia/, tone: "text-warning ring-warning/30 border-warning/30", font: "font-bold" },
    { test: /lionsgate/, tone: "text-zinc-100 ring-zinc-300/30 border-zinc-300/25", font: "font-bold uppercase tracking-wider" },
    { test: /^a24$/, label: "A24", tone: "text-zinc-100 ring-zinc-300/35 border-zinc-300/30", font: "font-black tracking-[0.16em]" },
    // Chaînes françaises courantes dans Sonarr.
    { test: /\barte\b/, label: "ARTE", tone: "text-orange-300 ring-orange-400/40 border-orange-400/35", font: "font-black tracking-[0.12em]" },
    { test: /\btf1\b/, label: "TF1", tone: "text-blue-200 ring-blue-400/40 border-blue-400/35", font: "font-black" },
    { test: /^france\s?[2-5]$|france t[ée]l[ée]visions|france\.tv/, tone: "text-sky-200 ring-primary/35 border-sky-400/30", font: "font-bold" },
    { test: /^m6$/, label: "M6", tone: "text-zinc-100 ring-zinc-300/35 border-zinc-300/30", font: "font-black" },
    { test: /\bocs\b/, label: "OCS", tone: "text-orange-200 ring-orange-400/40 border-orange-400/35", font: "font-black tracking-wider" },
    { test: /gaumont|path[ée]/, tone: "text-destructive ring-destructive/35 border-destructive/30", font: "font-bold" },
];

const NEUTRAL = { tone: "text-white/75 ring-white/15 border-white/10", font: "font-semibold" };

/** Marque reconnue (libellé + style) ou style neutre avec le nom d'origine. */
function resolveBrand(name: string) {
    const lower = name.toLowerCase().trim();
    const brand = BRANDS.find((b) => b.test.test(lower));
    return {
        label: brand?.label ?? name.trim(),
        tone: brand?.tone ?? NEUTRAL.tone,
        font: brand?.font ?? NEUTRAL.font,
    };
}

export interface StudioNetworkLogoProps {
    name?: string | null;
    /** "studio" (film) ou "network" (série) : choisit l'icône et le libellé lu. */
    kind?: "studio" | "network";
    variant?: "mini" | "hero";
    className?: string;
}

export function StudioNetworkLogo({ name, kind = "studio", variant = "mini", className }: StudioNetworkLogoProps) {
    if (!name || !name.trim()) return null;
    const { label, tone, font } = resolveBrand(name);
    const what = kind === "network" ? "Chaîne" : "Studio";

    if (variant === "hero") {
        const Icon = kind === "network" ? Tv : Building2;
        return (
            <span
                title={`${what} : ${name}`}
                className={cn(
                    "inline-flex max-w-full items-center gap-1.5 rounded-full border bg-white/[0.04] px-2.5 py-1 text-xs backdrop-blur-md",
                    tone,
                    className,
                )}
            >
                <Icon className="h-3.5 w-3.5 shrink-0 opacity-75" aria-hidden />
                <span className="sr-only">{what} : </span>
                <span className={cn("truncate", font)}>{label}</span>
            </span>
        );
    }

    // "mini" : ne doit jamais élargir la carte → tronqué, nom complet en infobulle.
    return (
        <span
            title={`${what} : ${name}`}
            className={cn(
                "inline-block min-w-0 max-w-full truncate rounded px-1.5 py-px align-middle text-[9px] leading-tight ring-1 backdrop-blur-sm bg-black/55",
                tone,
                font,
                className,
            )}
        >
            <span className="sr-only">{what} : </span>
            {label}
        </span>
    );
}
