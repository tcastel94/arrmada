"use client";

/**
 * Onglet « Assistant » de /trash-guides : 5 questions sur ton matériel
 * puis les profils TRaSH recommandés, applicables à Sonarr/Radarr.
 * ----------------------------------------------------------------
 * Corrections par rapport à l'ancienne page :
 *  - réponses mémorisées dans le navigateur (localStorage, protégé par
 *    try/catch : navigation privée, stockage bloqué…) ;
 *  - langue par défaut « Multi » (cohérent avec « meilleur choix ») ;
 *  - les anciennes recommandations sont effacées pendant le recalcul
 *    (avant, on voyait les recos d'avant en croyant voir les nouvelles) ;
 *  - erreurs affichées avec un bouton « Réessayer », plus de console.log ;
 *  - la modale d'application est un vrai Dialog (cf. ApplyDialog).
 */
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, ArrowRight, Check, ChevronDown, Film, Shield, Tv, Zap, type LucideIcon } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { ErrorState, EmptyState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { GradientProgress } from "@/components/fx/gradient-progress";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useTrashRecommend, type MediaPreferences, type RecommendedProfile } from "@/hooks/use-trash-guides";
import { EASE_OUT, SPRING, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";
import {
    AUDIO_OPTIONS,
    CF_CATEGORY,
    CF_FALLBACK,
    CONTENT_TOGGLES,
    DEFAULT_PREFS,
    DISPLAY_OPTIONS,
    LANGUAGE_OPTIONS,
    QUALITY_OPTIONS,
    STEPS,
    type WizardOption,
} from "./wizard-options";
import { ApplyDialog } from "./apply-dialog";

const STORAGE_KEY = "arrmada:trash-wizard-prefs";

/**
 * Glissement latéral selon le sens de navigation. `custom` est transmis
 * par AnimatePresence à l'élément SORTANT aussi : il part du bon côté
 * même si le sens a changé entre-temps.
 */
const slide = {
    enter: (d: number) => ({ opacity: 0, x: 28 * d }),
    center: { opacity: 1, x: 0 },
    exit: (d: number) => ({ opacity: 0, x: -28 * d }),
};
const REVIEW_STEP = STEPS.length - 1;

/** Relit les préférences mémorisées en ignorant toute valeur invalide. */
function loadPrefs(): MediaPreferences {
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        if (!raw) return DEFAULT_PREFS;
        const saved = JSON.parse(raw) as Partial<MediaPreferences>;
        const pick = <K extends keyof MediaPreferences>(key: K, allowed: readonly MediaPreferences[K][]) =>
            allowed.includes(saved[key] as MediaPreferences[K]) ? (saved[key] as MediaPreferences[K]) : DEFAULT_PREFS[key];
        return {
            display_type: pick("display_type", DISPLAY_OPTIONS.map((o) => o.value)),
            audio_type: pick("audio_type", AUDIO_OPTIONS.map((o) => o.value)),
            language: pick("language", LANGUAGE_OPTIONS.map((o) => o.value)),
            quality: pick("quality", QUALITY_OPTIONS.map((o) => o.value)),
            watches_anime: typeof saved.watches_anime === "boolean" ? saved.watches_anime : false,
            watches_french_series: typeof saved.watches_french_series === "boolean" ? saved.watches_french_series : false,
        };
    } catch {
        return DEFAULT_PREFS;
    }
}

export function TrashWizard() {
    const [step, setStep] = useState(0);
    const [direction, setDirection] = useState(1);
    const [prefs, setPrefs] = useState<MediaPreferences>(DEFAULT_PREFS);
    const [loaded, setLoaded] = useState(false);
    const [applyOpen, setApplyOpen] = useState(false);
    const recommend = useTrashRecommend();

    // Lecture des préférences au montage (côté navigateur uniquement).
    useEffect(() => {
        setPrefs(loadPrefs());
        setLoaded(true);
    }, []);

    // Sauvegarde à chaque changement (après la lecture initiale).
    useEffect(() => {
        if (!loaded) return;
        try {
            window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
        } catch {
            /* stockage indisponible : la préférence ne sera simplement pas retenue */
        }
    }, [prefs, loaded]);

    const update = <K extends keyof MediaPreferences>(key: K, value: MediaPreferences[K]) =>
        setPrefs((p) => ({ ...p, [key]: value }));

    /** Lance le calcul en effaçant d'abord le résultat précédent. */
    const fetchRecommendations = () => {
        recommend.reset();
        recommend.mutate(prefs);
    };

    const goTo = (target: number) => {
        if (target === step) return;
        setDirection(target > step ? 1 : -1);
        setStep(target);
        if (target === REVIEW_STEP) fetchRecommendations();
    };

    const current = STEPS[step];
    const recs: RecommendedProfile[] = recommend.data ?? [];

    return (
        <div className="space-y-5">
            {/* Barre d'étapes */}
            <div className="glass rounded-2xl p-3">
                <div className="scrollbar-none flex gap-1 overflow-x-auto">
                    {STEPS.map((s, i) => {
                        const active = i === step;
                        const done = i < step;
                        const Icon = done ? Check : s.icon;
                        return (
                            <button
                                key={s.id}
                                type="button"
                                onClick={() => goTo(i)}
                                aria-current={active ? "step" : undefined}
                                className={cn(
                                    "relative flex min-w-[3rem] flex-1 items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-medium transition-colors",
                                    active ? "text-white" : done ? "text-orange-200 hover:text-white" : "text-muted-foreground hover:text-foreground",
                                )}
                            >
                                {active && (
                                    <motion.span
                                        layoutId="trash-step"
                                        transition={SPRING}
                                        className="absolute inset-0 rounded-xl bg-gradient-to-r from-orange-500/80 to-amber-500/70 shadow-[0_0_24px_-6px_hsl(24_95%_58%/0.8)]"
                                    />
                                )}
                                <Icon className="relative h-3.5 w-3.5 shrink-0" />
                                <span className="relative hidden sm:inline">{s.title}</span>
                            </button>
                        );
                    })}
                </div>
                <GradientProgress value={(step / REVIEW_STEP) * 100} tone="amber" className="mt-3 h-1" />
            </div>

            {/* Contenu de l'étape */}
            <Panel
                title={current.question}
                icon={current.icon}
                iconClassName="text-orange-300"
                action={<span className="text-xs text-muted-foreground tabular-nums">{step + 1}/{STEPS.length}</span>}
            >
                <p className="-mt-1 mb-4 text-sm text-muted-foreground">{current.help}</p>
                <AnimatePresence mode="wait" custom={direction} initial={false}>
                    <motion.div
                        key={step}
                        custom={direction}
                        variants={slide}
                        initial="enter"
                        animate="center"
                        exit="exit"
                        transition={{ duration: 0.28, ease: EASE_OUT }}
                    >
                        {step === 0 && (
                            <OptionGrid
                                id="display"
                                options={DISPLAY_OPTIONS}
                                value={prefs.display_type}
                                onChange={(v) => update("display_type", v)}
                                cols="sm:grid-cols-3"
                            />
                        )}
                        {step === 1 && (
                            <OptionGrid id="audio" options={AUDIO_OPTIONS} value={prefs.audio_type} onChange={(v) => update("audio_type", v)} />
                        )}
                        {step === 2 && (
                            <OptionGrid id="language" options={LANGUAGE_OPTIONS} value={prefs.language} onChange={(v) => update("language", v)} />
                        )}
                        {step === 3 && (
                            <OptionGrid id="quality" options={QUALITY_OPTIONS} value={prefs.quality} onChange={(v) => update("quality", v)} />
                        )}
                        {step === 4 && (
                            <div className="space-y-3">
                                {CONTENT_TOGGLES.map((t) => (
                                    <label
                                        key={t.key}
                                        className={cn(
                                            "flex cursor-pointer items-center gap-4 rounded-2xl p-4 ring-1 transition-all",
                                            prefs[t.key]
                                                ? "bg-orange-500/10 ring-orange-400/40 shadow-[0_0_30px_-12px_hsl(24_95%_58%/0.7)]"
                                                : "bg-white/[0.025] ring-white/[0.06] hover:ring-white/[0.12]",
                                        )}
                                    >
                                        <IconTile icon={t.icon} active={prefs[t.key]} />
                                        <span className="min-w-0 flex-1">
                                            <span className="block text-sm font-semibold">{t.label}</span>
                                            <span className="block text-xs text-muted-foreground">{t.desc}</span>
                                        </span>
                                        <Switch checked={prefs[t.key]} onCheckedChange={(v) => update(t.key, v)} aria-label={t.label} />
                                    </label>
                                ))}
                            </div>
                        )}
                        {step === REVIEW_STEP && (
                            <ReviewStep
                                prefs={prefs}
                                recs={recs}
                                pending={recommend.isPending}
                                error={recommend.isError ? recommend.error : null}
                                onRetry={fetchRecommendations}
                                onEdit={goTo}
                            />
                        )}
                    </motion.div>
                </AnimatePresence>
            </Panel>

            {/* Navigation */}
            <div className="flex items-center justify-between gap-3">
                <Button variant="outline" onClick={() => goTo(step - 1)} disabled={step === 0}>
                    <ArrowLeft />
                    Précédent
                </Button>
                {step < REVIEW_STEP ? (
                    <Button onClick={() => goTo(step + 1)}>
                        {step === REVIEW_STEP - 1 ? "Voir mes recommandations" : "Suivant"}
                        <ArrowRight />
                    </Button>
                ) : (
                    <Button disabled={recommend.isPending || recs.length === 0} onClick={() => setApplyOpen(true)}>
                        <Zap />
                        Appliquer…
                    </Button>
                )}
            </div>

            <ApplyDialog open={applyOpen} onOpenChange={setApplyOpen} recommendations={recs} />
        </div>
    );
}

/* ── Sous-composants ───────────────────────────────────────── */

function IconTile({ icon: Icon, active }: { icon: LucideIcon; active: boolean }) {
    return (
        <span
            className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ring-1 transition-all",
                active
                    ? "from-orange-500/35 to-amber-500/10 text-orange-200 ring-orange-400/40"
                    : "from-white/[0.06] to-transparent text-muted-foreground ring-white/[0.08]",
            )}
        >
            <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
    );
}

/**
 * Grille de choix exclusifs. La surbrillance de la carte choisie glisse
 * d'une carte à l'autre (`layoutId` propre à chaque question).
 */
function OptionGrid<V extends string>({
    id,
    options,
    value,
    onChange,
    cols = "",
}: {
    id: string;
    options: WizardOption<V>[];
    value: V;
    onChange: (v: V) => void;
    cols?: string;
}) {
    return (
        <motion.div variants={stagger(0, 0.04)} initial="hidden" animate="show" role="radiogroup" className={cn("grid grid-cols-1 gap-3 min-[420px]:grid-cols-2", cols)}>
            {options.map((opt) => {
                const selected = opt.value === value;
                return (
                    <motion.button
                        key={opt.value}
                        type="button"
                        role="radio"
                        aria-checked={selected}
                        variants={fadeUp}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => onChange(opt.value)}
                        className={cn(
                            "relative flex items-center gap-3 rounded-2xl p-4 text-left ring-1 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400/70",
                            selected ? "ring-orange-400/50" : "bg-white/[0.025] ring-white/[0.06] hover:bg-white/[0.045] hover:ring-white/[0.12]",
                        )}
                    >
                        {selected && (
                            <motion.span
                                layoutId={`trash-opt-${id}`}
                                transition={SPRING}
                                className="absolute inset-0 rounded-2xl bg-gradient-to-br from-orange-500/15 to-amber-500/[0.04] shadow-[0_0_34px_-12px_hsl(24_95%_58%/0.8)]"
                            />
                        )}
                        <span className="relative">
                            <IconTile icon={opt.icon} active={selected} />
                        </span>
                        <span className="relative min-w-0 flex-1">
                            <span className="flex flex-wrap items-center gap-1.5 text-sm font-semibold">
                                {opt.label}
                                {opt.recommended && (
                                    <span className="rounded-md bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-300">
                                        Recommandé
                                    </span>
                                )}
                            </span>
                            <span className="mt-0.5 block text-xs text-muted-foreground">{opt.desc}</span>
                        </span>
                        {selected && (
                            <motion.span
                                initial={{ scale: 0 }}
                                animate={{ scale: 1 }}
                                transition={SPRING}
                                className="relative flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-orange-500 text-white"
                            >
                                <Check className="h-3 w-3" strokeWidth={3} />
                            </motion.span>
                        )}
                    </motion.button>
                );
            })}
        </motion.div>
    );
}

function ReviewStep({
    prefs,
    recs,
    pending,
    error,
    onRetry,
    onEdit,
}: {
    prefs: MediaPreferences;
    recs: RecommendedProfile[];
    pending: boolean;
    error: Error | null;
    onRetry: () => void;
    onEdit: (step: number) => void;
}) {
    // Résumé des choix : chaque pastille ramène à l'étape correspondante.
    const choices: { step: number; label: string; icon: LucideIcon }[] = [
        { step: 0, ...pickOpt(DISPLAY_OPTIONS, prefs.display_type) },
        { step: 1, ...pickOpt(AUDIO_OPTIONS, prefs.audio_type) },
        { step: 2, ...pickOpt(LANGUAGE_OPTIONS, prefs.language) },
        { step: 3, ...pickOpt(QUALITY_OPTIONS, prefs.quality) },
        ...CONTENT_TOGGLES.filter((t) => prefs[t.key]).map((t) => ({ step: 4, label: t.label, icon: t.icon })),
    ];

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
                {choices.map((c) => (
                    <button key={`${c.step}:${c.label}`} type="button" className="chip" onClick={() => onEdit(c.step)} title="Modifier">
                        <c.icon className="h-3.5 w-3.5 text-orange-300" />
                        {c.label}
                    </button>
                ))}
            </div>

            {pending ? (
                <div className="space-y-3" aria-busy>
                    {Array.from({ length: 2 }).map((_, i) => (
                        <div key={i} className="space-y-3 rounded-2xl bg-white/[0.025] p-4 ring-1 ring-white/[0.05]">
                            <Shimmer className="h-4 w-56 rounded-md" />
                            <Shimmer className="h-3 w-full max-w-md rounded-md" />
                            <div className="flex flex-wrap gap-1.5">
                                {Array.from({ length: 10 }).map((__, j) => (
                                    <Shimmer key={j} className="h-5 w-20 rounded-md" />
                                ))}
                            </div>
                        </div>
                    ))}
                    <p className="text-center text-xs text-muted-foreground">Calcul des recommandations…</p>
                </div>
            ) : error ? (
                <ErrorState
                    compact
                    error={error}
                    onRetry={onRetry}
                    title="Impossible de générer les recommandations"
                />
            ) : recs.length === 0 ? (
                <EmptyState
                    compact
                    icon={Shield}
                    title="Aucune recommandation"
                    description="Synchronise les données TRaSH (bouton en haut de page) puis réessaie."
                    action={{ label: "Réessayer", onClick: onRetry }}
                />
            ) : (
                <motion.ul variants={stagger(0, 0.08)} initial="hidden" animate="show" className="space-y-3">
                    {recs.map((rec) => (
                        <RecommendationCard key={`${rec.service_type}-${rec.profile_id}`} rec={rec} />
                    ))}
                </motion.ul>
            )}
        </div>
    );
}

function pickOpt<V extends string>(options: WizardOption<V>[], value: V) {
    const o = options.find((x) => x.value === value) ?? options[0];
    return { label: o.label, icon: o.icon };
}

const CF_PREVIEW = 24;

function RecommendationCard({ rec }: { rec: RecommendedProfile }) {
    const [expanded, setExpanded] = useState(false);
    const isSonarr = rec.service_type === "sonarr";
    const Icon = isSonarr ? Tv : Film;
    const visible = expanded ? rec.custom_formats : rec.custom_formats.slice(0, CF_PREVIEW);
    const categories = Array.from(new Set(rec.custom_formats.map((cf) => cf.category)));

    return (
        <motion.li variants={fadeUp} className="rounded-2xl bg-white/[0.025] p-4 ring-1 ring-white/[0.06]">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-3">
                    <span
                        className={cn(
                            "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1",
                            isSonarr ? "bg-sky-500/15 text-sky-300 ring-sky-400/25" : "bg-violet-500/15 text-violet-300 ring-violet-400/25",
                        )}
                    >
                        <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                        <p className="text-sm font-semibold">
                            {isSonarr ? "Sonarr" : "Radarr"} · <span className="font-mono text-xs">{rec.profile_name}</span>
                        </p>
                        {rec.description && <p className="mt-0.5 text-xs text-muted-foreground">{rec.description}</p>}
                    </div>
                </div>
                <span className="rounded-lg bg-orange-500/15 px-2 py-0.5 text-xs font-semibold text-orange-300 tabular-nums">
                    {rec.custom_formats.length} formats
                </span>
            </div>

            {/* Légende des catégories (la couleur n'est jamais seule porteuse de sens) */}
            <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
                {categories.map((c) => {
                    const meta = CF_CATEGORY[c] ?? CF_FALLBACK;
                    return (
                        <span key={c} className="flex items-center gap-1">
                            <span className={cn("h-2.5 w-2.5 rounded-[3px] border", meta.cls)} />
                            {meta.label}
                        </span>
                    );
                })}
            </div>

            <div className="mt-2 flex flex-wrap gap-1.5">
                {visible.map((cf) => (
                    <span
                        key={cf.trash_id}
                        title={(CF_CATEGORY[cf.category] ?? CF_FALLBACK).label}
                        className={cn("rounded-md border px-1.5 py-0.5 font-mono text-[10px]", (CF_CATEGORY[cf.category] ?? CF_FALLBACK).cls)}
                    >
                        {cf.name}
                    </span>
                ))}
                {rec.custom_formats.length > CF_PREVIEW && (
                    <button
                        type="button"
                        onClick={() => setExpanded((e) => !e)}
                        className="inline-flex items-center gap-1 rounded-md border border-white/10 px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:text-foreground"
                    >
                        <ChevronDown className={cn("h-3 w-3 transition-transform", expanded && "rotate-180")} />
                        {expanded ? "Réduire" : `+${rec.custom_formats.length - CF_PREVIEW} autres`}
                    </button>
                )}
            </div>
        </motion.li>
    );
}
