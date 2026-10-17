"use client";

/**
 * Assistant d'installation (premier lancement, hors coquille applicative).
 * ----------------------------------------------------------------
 * 5 étapes : Bienvenue → Sécurité (mot de passe admin) → Découverte réseau
 * → Services → Terminé.
 * Sécurité : le mot de passe est créé ICI (plus de ARRMADA_AUTH_SECRET à
 * écrire dans un .env). L'API ouvre la session dans la foulée, donc la
 * fin de l'assistant mène directement au tableau de bord.
 * Corrections par rapport à l'ancienne version :
 *  - libellés d'étapes enfin affichés, stepper animé ;
 *  - liste des types dérivée de SERVICE_META (plus de copie locale) ;
 *  - lignes incomplètes signalées (avant : ignorées EN SILENCE à l'envoi) ;
 *  - bouton « Tester » par ligne ; port pré-rempli selon le type ;
 *  - erreurs du backend traduites ; identifiants de ligne stables (plus
 *    de key={index}) ; plus de `any` ;
 *  - le bouton final mène à la connexion et s'appelle « Se connecter ».
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import {
    AlertCircle,
    ArrowRight,
    Check,
    CheckCircle2,
    ChevronLeft,
    KeyRound,
    LayoutDashboard,
    Loader2,
    LockKeyhole,
    LogIn,
    Network,
    Plus,
    Radar,
    RefreshCw,
    Rocket,
    Server,
    ShieldCheck,
    Sparkles,
    Trash2,
    XCircle,
    Zap,
    type LucideIcon,
} from "lucide-react";
import { CreatePasswordForm } from "@/components/auth/create-password-form";
import { StackWiring } from "@/components/stack/stack-wiring";
import { AuroraBackground } from "@/components/fx/aurora-background";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { FormField, SecretInput, validateHttpUrl } from "@/components/settings/form-field";
import { TypeIcon } from "@/components/services/service-config";
import {
    API_KEY_HINTS,
    SERVICE_TYPE_OPTIONS,
    exampleUrl,
    serviceVisual,
    swapDefaultPort,
} from "@/components/services/service-meta";
import {
    completeSetup,
    discoverServices,
    testSetupService,
    useSetupStatus,
    type DiscoveredService,
    type ServiceSetupItem,
    type SetupTestResult,
} from "@/hooks/use-setup";
import { isAuthenticated } from "@/lib/api-client";
import { plural } from "@/lib/format";
import { EASE_OUT, SPRING, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

/* ── Étapes ─────────────────────────────────────────────────── */

const STEPS: { title: string; icon: LucideIcon }[] = [
    { title: "Bienvenue", icon: Sparkles },
    { title: "Sécurité", icon: LockKeyhole },
    { title: "Découverte", icon: Radar },
    { title: "Services", icon: Server },
    { title: "Terminé", icon: Rocket },
];

/** Glissement horizontal selon le sens de navigation (suivant / retour). */
const slide: Variants = {
    enter: (dir: number) => ({ opacity: 0, x: dir >= 0 ? 48 : -48, filter: "blur(4px)" }),
    center: { opacity: 1, x: 0, filter: "blur(0px)", transition: { duration: 0.45, ease: EASE_OUT } },
    exit: (dir: number) => ({ opacity: 0, x: dir >= 0 ? -48 : 48, filter: "blur(4px)", transition: { duration: 0.25 } }),
};

/** Une ligne de service en cours de saisie (id stable pour React). */
interface Row extends ServiceSetupItem {
    id: string;
    /** Vrai dès que l'utilisateur a tapé un nom (sinon le nom suit le type). */
    nameTouched: boolean;
}

interface RowErrors {
    name?: string;
    url?: string;
    api_key?: string;
}

function validateRow(r: Row): RowErrors {
    const e: RowErrors = {};
    if (!r.name.trim()) e.name = "Nom obligatoire.";
    const urlErr = validateHttpUrl(r.url, exampleUrl(r.type));
    if (urlErr) e.url = urlErr;
    if (!r.api_key.trim()) e.api_key = "Clé API obligatoire.";
    return e;
}

export default function SetupPage() {
    const router = useRouter();
    const { data: status, isLoading, isError, error, refetch, isFetching } = useSetupStatus();
    const [[step, direction], setStepState] = useState<[number, number]>([0, 0]);
    const goTo = (next: number) => setStepState(([cur]) => [next, next > cur ? 1 : -1]);

    // Découverte
    const [scanning, setScanning] = useState(false);
    const [scanError, setScanError] = useState("");
    const [discovered, setDiscovered] = useState<DiscoveredService[] | null>(null);
    const [picked, setPicked] = useState<Set<string>>(new Set());

    // Saisie des services
    const idCounter = useRef(0);
    const newId = () => `row-${++idCounter.current}`;
    const [rows, setRows] = useState<Row[]>([]);
    const [showErrors, setShowErrors] = useState(false);
    const [tests, setTests] = useState<Record<string, { pending: boolean; result?: SetupTestResult }>>({});
    const [submitting, setSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState("");
    const [added, setAdded] = useState(0);

    // Déjà configuré → direction le tableau de bord (qui renverra au login si besoin).
    useEffect(() => {
        if (status?.is_configured && step !== 4) router.replace("/dashboard");
    }, [status, router, step]);

    const discoveredKey = (d: DiscoveredService) => `${d.type}:${d.url}`;

    /* ── Découverte réseau ──────────────────────────────────── */
    const handleScan = useCallback(async () => {
        setScanning(true);
        setScanError("");
        try {
            const results = await discoverServices();
            setDiscovered(results);
            // Tout est coché par défaut : l'utilisateur décoche ce qu'il ne veut pas.
            setPicked(new Set(results.map(discoveredKey)));
        } catch (e) {
            setScanError(e instanceof Error ? e.message : "La détection réseau a échoué.");
        } finally {
            setScanning(false);
        }
    }, []);

    const blankRow = (type = "sonarr"): Row => ({
        id: newId(),
        name: serviceVisual(type).label,
        type,
        url: "",
        api_key: "",
        is_enabled: true,
        nameTouched: false,
    });

    /** Passe à l'étape 2 en ajoutant les services cochés (sans doublon). */
    const continueToServices = () => {
        const chosen = (discovered ?? []).filter((d) => picked.has(discoveredKey(d)));
        setRows((prev) => {
            const existing = new Set(prev.map((r) => `${r.type}:${r.url}`));
            const fresh: Row[] = chosen
                .filter((d) => !existing.has(discoveredKey(d)))
                .map((d) => ({
                    id: newId(),
                    name: d.name,
                    type: d.type,
                    url: d.url,
                    api_key: "",
                    is_enabled: true,
                    nameTouched: true,
                }));
            const next = [...prev, ...fresh];
            return next.length > 0 ? next : [blankRow()];
        });
        goTo(3);
    };

    /* ── Édition des lignes ─────────────────────────────────── */
    const updateRow = <K extends keyof Row>(id: string, field: K, value: Row[K]) => {
        setRows((prev) => prev.map((r) => (r.id === id ? { ...r, [field]: value } : r)));
        // Toute modification invalide le résultat de test précédent.
        setTests((t) => {
            if (!t[id]) return t;
            const copy = { ...t };
            delete copy[id];
            return copy;
        });
    };

    const changeType = (id: string, type: string) => {
        setRows((prev) =>
            prev.map((r) =>
                r.id === id
                    ? {
                          ...r,
                          type,
                          url: swapDefaultPort(r.url, r.type, type),
                          name: r.nameTouched ? r.name : serviceVisual(type).label,
                      }
                    : r,
            ),
        );
        setTests((t) => {
            const copy = { ...t };
            delete copy[id];
            return copy;
        });
    };

    const removeRow = (id: string) => setRows((prev) => prev.filter((r) => r.id !== id));

    const testRow = async (row: Row) => {
        if (validateHttpUrl(row.url)) {
            setTests((t) => ({ ...t, [row.id]: { pending: false, result: { ok: false, label: "Saisis d'abord une adresse valide." } } }));
            return;
        }
        setTests((t) => ({ ...t, [row.id]: { pending: true } }));
        try {
            const result = await testSetupService(row);
            setTests((t) => ({ ...t, [row.id]: { pending: false, result } }));
        } catch (e) {
            setTests((t) => ({
                ...t,
                [row.id]: { pending: false, result: { ok: false, label: e instanceof Error ? e.message : "Test impossible." } },
            }));
        }
    };

    const errorsById = useMemo(() => Object.fromEntries(rows.map((r) => [r.id, validateRow(r)])), [rows]);
    const invalidCount = rows.filter((r) => Object.keys(errorsById[r.id] ?? {}).length > 0).length;
    const readyCount = rows.length - invalidCount;

    /* ── Envoi ──────────────────────────────────────────────── */
    const handleComplete = async () => {
        setShowErrors(true);
        setSubmitError("");
        if (rows.length === 0) {
            setSubmitError("Ajoute au moins un service.");
            return;
        }
        if (invalidCount > 0) {
            setSubmitError(
                `${plural(invalidCount, "service incomplet", "services incomplets")} : complète les champs en rouge ou retire la ligne.`,
            );
            return;
        }
        setSubmitting(true);
        try {
            const res = await completeSetup(
                rows.map(({ name, type, url, api_key, is_enabled }) => ({
                    name: name.trim(),
                    type,
                    url: url.trim().replace(/\/+$/, ""),
                    api_key: api_key.trim(),
                    is_enabled,
                })),
            );
            setAdded(res?.services_added ?? rows.length);
            goTo(4);
        } catch (e) {
            setSubmitError(e instanceof Error ? e.message : "La configuration a échoué.");
        } finally {
            setSubmitting(false);
        }
    };

    /* ── Rendu ──────────────────────────────────────────────── */
    return (
        <div className="relative min-h-screen overflow-x-hidden">
            <AuroraBackground intense />
            <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center px-4 pb-10 pt-8 sm:pt-12">
                <BrandMark />

                {isLoading ? (
                    <div className="mt-10 flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" /> Préparation de l&apos;équipage…
                    </div>
                ) : isError ? (
                    <div className="glass-strong mt-10 w-full max-w-md rounded-3xl p-6 text-center">
                        <AlertCircle className="mx-auto h-8 w-8 text-red-400" />
                        <p className="mt-3 font-semibold">Backend injoignable</p>
                        <p className="mt-1 text-sm text-muted-foreground">{error instanceof Error ? error.message : ""}</p>
                        <Button className="mt-5" onClick={() => refetch()} disabled={isFetching}>
                            <RefreshCw className={isFetching ? "animate-spin" : ""} /> Réessayer
                        </Button>
                    </div>
                ) : (
                    <>
                        <Stepper step={step} />
                        <div className="relative mt-6 w-full">
                            <AnimatePresence mode="wait" custom={direction} initial={false}>
                                <motion.section
                                    key={step}
                                    custom={direction}
                                    variants={slide}
                                    initial="enter"
                                    animate="center"
                                    exit="exit"
                                    className="glass-strong border-gradient w-full rounded-3xl p-5 sm:p-8"
                                >
                                    {step === 0 && <WelcomeStep databaseType={status?.database_type} onStart={() => goTo(1)} />}

                                    {step === 1 && (
                                        <SecurityStep
                                            passwordSet={!!status?.password_set}
                                            onCreated={() => {
                                                void refetch();
                                                goTo(2);
                                            }}
                                            onBack={() => goTo(0)}
                                            onContinue={() => goTo(2)}
                                        />
                                    )}

                                    {step === 2 && (
                                        <DiscoveryStep
                                            scanning={scanning}
                                            scanError={scanError}
                                            discovered={discovered}
                                            picked={picked}
                                            keyOf={discoveredKey}
                                            onScan={handleScan}
                                            onToggle={(k) =>
                                                setPicked((prev) => {
                                                    const next = new Set(prev);
                                                    if (next.has(k)) next.delete(k);
                                                    else next.add(k);
                                                    return next;
                                                })
                                            }
                                            onBack={() => goTo(1)}
                                            onContinue={continueToServices}
                                            onImported={(count) => {
                                                setAdded(count);
                                                void refetch();
                                                goTo(4);
                                            }}
                                        />
                                    )}

                                    {step === 3 && (
                                        <div className="space-y-5">
                                            <StepTitle
                                                icon={Server}
                                                title="Tes services"
                                                description="Renseigne l'adresse et la clé API de chaque application. Tu pourras en ajouter d'autres plus tard dans Paramètres."
                                            />
                                            <motion.div layout className="space-y-3">
                                                <AnimatePresence initial={false}>
                                                    {rows.map((row, i) => (
                                                        <ServiceRow
                                                            key={row.id}
                                                            index={i}
                                                            row={row}
                                                            errors={showErrors ? errorsById[row.id] : undefined}
                                                            test={tests[row.id]}
                                                            canRemove={rows.length > 1}
                                                            onChange={updateRow}
                                                            onTypeChange={changeType}
                                                            onRemove={removeRow}
                                                            onTest={testRow}
                                                        />
                                                    ))}
                                                </AnimatePresence>
                                            </motion.div>

                                            <Button variant="outline" onClick={() => setRows((p) => [...p, blankRow()])} className="w-full border-dashed">
                                                <Plus /> Ajouter un service
                                            </Button>

                                            <div className="flex flex-wrap items-center gap-2 text-xs">
                                                <span className="chip">
                                                    <CheckCircle2 className="h-3 w-3 text-emerald-400" /> {plural(readyCount, "prêt", "prêts")}
                                                </span>
                                                {invalidCount > 0 && (
                                                    <span className="chip">
                                                        <AlertCircle className="h-3 w-3 text-amber-400" /> {plural(invalidCount, "incomplet", "incomplets")}
                                                    </span>
                                                )}
                                            </div>

                                            <AnimatePresence>
                                                {submitError && (
                                                    <motion.p
                                                        initial={{ opacity: 0, y: -4 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        exit={{ opacity: 0 }}
                                                        role="alert"
                                                        className="flex items-start gap-2 rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300"
                                                    >
                                                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {submitError}
                                                    </motion.p>
                                                )}
                                            </AnimatePresence>

                                            <div className="flex flex-col-reverse gap-2 border-t border-white/[0.06] pt-5 sm:flex-row">
                                                <Button variant="ghost" onClick={() => goTo(2)}>
                                                    <ChevronLeft /> Retour
                                                </Button>
                                                <Button onClick={handleComplete} disabled={submitting} size="lg" className="sm:ml-auto">
                                                    {submitting ? <Loader2 className="animate-spin" /> : <Check />}
                                                    {submitting ? "Installation…" : "Terminer l'installation"}
                                                </Button>
                                            </div>
                                        </div>
                                    )}

                                    {step === 4 && (
                                        <DoneStep
                                            added={added}
                                            loggedIn={isAuthenticated()}
                                            onOpen={() => router.push(isAuthenticated() ? "/dashboard" : "/login")}
                                        />
                                    )}
                                </motion.section>
                            </AnimatePresence>
                        </div>
                    </>
                )}
            </main>
        </div>
    );
}

/* ── Logo lumineux ──────────────────────────────────────────── */

function BrandMark() {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 18 }}
            className="flex flex-col items-center gap-3"
        >
            <div className="relative">
                {/* Halo en radial-gradient (et non `blur`) : l'animation pulse-glow
                    réécrit la propriété CSS `filter`, ce qui annulerait un flou. */}
                <div
                    aria-hidden
                    className="absolute inset-0 -m-10 animate-pulse-glow rounded-full"
                    style={{ background: "radial-gradient(closest-side, hsl(var(--primary) / 0.45), transparent)" }}
                />
                <div className="border-beam relative h-16 w-16 rounded-2xl p-[2px] sm:h-20 sm:w-20">
                    <div className="h-full w-full overflow-hidden rounded-[14px] sm:rounded-[18px]">
                        <Image src="/logo-mark.png" alt="ArrMada" width={80} height={80} priority className="h-full w-full object-cover" />
                    </div>
                </div>
            </div>
            <p className="text-lg font-bold tracking-tight">
                Arr<span className="text-gradient">Mada</span>
            </p>
        </motion.div>
    );
}

/* ── Stepper ────────────────────────────────────────────────── */

function Stepper({ step }: { step: number }) {
    return (
        <ol aria-label="Étapes de l'installation" className="mt-6 flex w-full max-w-xl items-start">
            {STEPS.map((s, i) => {
                const done = i < step;
                const active = i === step;
                const Icon = s.icon;
                return (
                    <li key={s.title} className="flex flex-1 items-start last:flex-none" aria-current={active ? "step" : undefined}>
                        <div className="flex w-16 flex-col items-center gap-1.5 sm:w-20">
                            <motion.div
                                initial={false}
                                animate={{ scale: active ? 1.08 : 1 }}
                                transition={SPRING}
                                className={cn(
                                    "relative flex h-10 w-10 items-center justify-center rounded-full border transition-colors duration-300",
                                    done && "border-primary/60 bg-primary text-primary-foreground",
                                    active && "border-primary/60 bg-primary/15 text-primary shadow-[0_0_24px_-4px_hsl(var(--primary)/0.8)]",
                                    !done && !active && "border-white/10 bg-white/[0.04] text-muted-foreground",
                                )}
                            >
                                {active && <span aria-hidden className="absolute inset-0 animate-pulse-ring rounded-full bg-primary/30" />}
                                <AnimatePresence mode="wait" initial={false}>
                                    <motion.span
                                        key={done ? "done" : "icon"}
                                        initial={{ scale: 0.4, opacity: 0 }}
                                        animate={{ scale: 1, opacity: 1 }}
                                        exit={{ scale: 0.4, opacity: 0 }}
                                        transition={{ duration: 0.2 }}
                                        className="relative"
                                    >
                                        {done ? <Check className="h-4 w-4" strokeWidth={3} /> : <Icon className="h-4 w-4" />}
                                    </motion.span>
                                </AnimatePresence>
                            </motion.div>
                            <span
                                className={cn(
                                    "text-center text-[11px] font-medium transition-colors",
                                    active ? "text-foreground" : done ? "text-primary" : "text-muted-foreground",
                                )}
                            >
                                {s.title}
                            </span>
                        </div>
                        {i < STEPS.length - 1 && (
                            <div aria-hidden className="relative mx-1 mt-5 h-0.5 flex-1 overflow-hidden rounded-full bg-white/10">
                                <motion.div
                                    className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-primary to-brand"
                                    initial={false}
                                    animate={{ width: done ? "100%" : "0%" }}
                                    transition={{ duration: 0.6, ease: EASE_OUT }}
                                />
                            </div>
                        )}
                    </li>
                );
            })}
        </ol>
    );
}

function StepTitle({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: string }) {
    return (
        <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25">
                <Icon className="h-5 w-5" />
            </span>
            <div>
                <h2 className="text-xl font-bold tracking-tight">{title}</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
            </div>
        </div>
    );
}

/* ── Étape 0 : Bienvenue ────────────────────────────────────── */

const FEATURES: { icon: LucideIcon; label: string; desc: string }[] = [
    { icon: Network, label: "Détection automatique", desc: "ArrMada scanne ton réseau pour trouver tes services." },
    { icon: Server, label: "Un seul tableau de bord", desc: "Sonarr, Radarr, Prowlarr, SABnzbd… réunis au même endroit." },
    { icon: Sparkles, label: "Recommandations", desc: "Des suggestions basées sur ta médiathèque." },
    { icon: ShieldCheck, label: "Sécurisé", desc: "Clés API chiffrées, session protégée par mot de passe." },
];

function WelcomeStep({ databaseType, onStart }: { databaseType?: string; onStart: () => void }) {
    return (
        <div className="space-y-7 text-center">
            <div>
                <h1 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
                    Bienvenue à bord <span className="text-gradient-animated">d&apos;ArrMada</span>
                </h1>
                <p className="mx-auto mt-2 max-w-md text-balance text-muted-foreground">
                    Le poste de commandement de ta stack *arr. Trois minutes pour tout connecter.
                </p>
            </div>
            <motion.div variants={stagger(0.15, 0.07)} initial="hidden" animate="show" className="grid grid-cols-1 gap-3 text-left sm:grid-cols-2">
                {FEATURES.map((f) => (
                    <motion.div key={f.label} variants={fadeUp} className="glass glass-hover flex items-start gap-3 rounded-2xl p-3.5">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
                            <f.icon className="h-4 w-4" />
                        </span>
                        <div>
                            <p className="text-sm font-semibold">{f.label}</p>
                            <p className="text-xs text-muted-foreground">{f.desc}</p>
                        </div>
                    </motion.div>
                ))}
            </motion.div>
            {databaseType && (
                <p className="text-xs text-muted-foreground">
                    Base de données : <span className="font-medium text-foreground">{databaseType === "postgresql" ? "PostgreSQL" : "SQLite"}</span>
                </p>
            )}
            <Button onClick={onStart} size="lg" className="w-full sm:w-auto sm:px-10">
                Commencer <ArrowRight />
            </Button>
        </div>
    );
}

/* ── Étape 1 : Sécurité ─────────────────────────────────────── */

function SecurityStep({
    passwordSet,
    onCreated,
    onBack,
    onContinue,
}: {
    passwordSet: boolean;
    onCreated: () => void;
    onBack: () => void;
    onContinue: () => void;
}) {
    return (
        <div className="space-y-5">
            <StepTitle
                icon={LockKeyhole}
                title="Mot de passe administrateur"
                description="Il protège l'accès à ArrMada (et à tes clés API). Tu pourras le changer plus tard dans Paramètres."
            />
            {passwordSet ? (
                <p className="flex items-start gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3.5 py-2.5 text-sm text-emerald-200">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> Un mot de passe est déjà défini pour cette instance.
                </p>
            ) : (
                <CreatePasswordForm onCreated={onCreated} submitLabel="Enregistrer et continuer" />
            )}
            <div className="flex flex-col-reverse gap-2 border-t border-white/[0.06] pt-5 sm:flex-row">
                <Button variant="ghost" onClick={onBack}>
                    <ChevronLeft /> Retour
                </Button>
                {passwordSet && (
                    <Button onClick={onContinue} className="sm:ml-auto">
                        Continuer <ArrowRight />
                    </Button>
                )}
            </div>
        </div>
    );
}

/* ── Étape 2 : Découverte ───────────────────────────────────── */

function DiscoveryStep({
    scanning,
    scanError,
    discovered,
    picked,
    keyOf,
    onScan,
    onToggle,
    onBack,
    onContinue,
    onImported,
}: {
    scanning: boolean;
    scanError: string;
    discovered: DiscoveredService[] | null;
    picked: Set<string>;
    keyOf: (d: DiscoveredService) => string;
    onScan: () => void;
    onToggle: (key: string) => void;
    onBack: () => void;
    onContinue: () => void;
    /** Import automatique réussi : nombre de services ajoutés à ArrMada. */
    onImported: (count: number) => void;
}) {
    const count = discovered?.filter((d) => picked.has(keyOf(d))).length ?? 0;
    // L'import lit des clés API : il exige la session ouverte à l'étape Sécurité.
    const canImport = isAuthenticated();
    return (
        <div className="space-y-5">
            <StepTitle
                icon={Radar}
                title="Découverte réseau"
                description="ArrMada peut scanner ton réseau local pour trouver Sonarr, Radarr, Prowlarr, SABnzbd… Tu peux aussi passer cette étape."
            />

            {canImport && (
                <div className="space-y-3 rounded-2xl border border-primary/20 bg-primary/[0.04] p-4">
                    <div>
                        <p className="text-sm font-semibold">Import automatique (recommandé)</p>
                        <p className="text-xs text-muted-foreground">
                            Clés API lues dans les fichiers de config de tes applis, puis Prowlarr, les clients de
                            téléchargement et Bazarr branchés entre eux.
                        </p>
                    </div>
                    <StackWiring
                        variant="wizard"
                        onApplied={(results) => {
                            const registered = results.filter((r) => r.ok && r.id.startsWith("register:")).length;
                            if (registered > 0) onImported(registered);
                        }}
                    />
                </div>
            )}

            <p className="eyebrow pt-1">{canImport ? "Ou scan réseau classique" : "Scan réseau"}</p>

            {/* Radar animé pendant le scan */}
            <AnimatePresence initial={false}>
                {scanning && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                    >
                        <div className="flex flex-col items-center py-6">
                            <div className="relative h-32 w-32">
                                {[0, 1, 2].map((i) => (
                                    <motion.span
                                        key={i}
                                        className="absolute inset-0 rounded-full border border-primary/40"
                                        initial={{ scale: 0.3, opacity: 0.9 }}
                                        animate={{ scale: 1.1, opacity: 0 }}
                                        transition={{ duration: 2.4, repeat: Infinity, delay: i * 0.8, ease: "easeOut" }}
                                    />
                                ))}
                                <div
                                    className="absolute inset-0 animate-spin rounded-full"
                                    style={{
                                        background: "conic-gradient(from 0deg, transparent 0deg, hsl(var(--primary) / 0.45) 50deg, transparent 90deg)",
                                        animationDuration: "2.2s",
                                    }}
                                />
                                <div className="absolute inset-[38%] flex items-center justify-center rounded-full bg-primary/20 ring-1 ring-primary/40">
                                    <Radar className="h-5 w-5 text-primary" />
                                </div>
                            </div>
                            <p className="mt-4 text-sm text-muted-foreground">Exploration du réseau local (une vingtaine de secondes)…</p>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {!scanning && (
                <Button onClick={onScan} variant={discovered ? "outline" : "default"} size="lg" className="w-full">
                    {discovered ? <RefreshCw /> : <Zap />}
                    {discovered ? "Relancer le scan" : "Scanner mon réseau"}
                </Button>
            )}

            {scanError && (
                <p role="alert" className="flex items-start gap-2 rounded-xl border border-red-500/25 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {scanError}
                </p>
            )}

            {discovered && !scanning && (
                discovered.length === 0 ? (
                    <p className="rounded-xl border border-white/[0.06] bg-background/30 px-4 py-3 text-sm text-muted-foreground">
                        Aucun service trouvé automatiquement. Pas de souci : tu vas pouvoir les saisir à la main.
                    </p>
                ) : (
                    <div className="space-y-2">
                        <p className="eyebrow">{plural(discovered.length, "service détecté", "services détectés")} — décoche ceux à ignorer</p>
                        <motion.ul variants={stagger(0, 0.05)} initial="hidden" animate="show" className="space-y-2">
                            {discovered.map((svc) => {
                                const k = keyOf(svc);
                                const on = picked.has(k);
                                return (
                                    <motion.li key={k} variants={fadeUp}>
                                        <button
                                            type="button"
                                            role="checkbox"
                                            aria-checked={on}
                                            onClick={() => onToggle(k)}
                                            className={cn(
                                                "flex w-full items-center gap-3 rounded-2xl border p-3 text-left transition-all",
                                                on ? "border-primary/35 bg-primary/[0.08]" : "border-white/[0.06] bg-background/30 opacity-60 hover:opacity-100",
                                            )}
                                        >
                                            <span
                                                className={cn(
                                                    "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                                                    on ? "border-primary bg-primary text-primary-foreground" : "border-white/20",
                                                )}
                                            >
                                                {on && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
                                            </span>
                                            <TypeIcon type={svc.type} className="h-9 w-9" />
                                            <span className="min-w-0 flex-1">
                                                <span className="block truncate text-sm font-semibold">{svc.name}</span>
                                                <span className="block truncate font-mono text-xs text-muted-foreground">{svc.url}</span>
                                            </span>
                                            <span className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
                                                {svc.version && <span className="font-mono text-[10px] text-muted-foreground">v{svc.version}</span>}
                                                <span
                                                    className={cn(
                                                        "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                                                        svc.needs_api_key ? "bg-amber-500/15 text-amber-300" : "bg-emerald-500/15 text-emerald-300",
                                                    )}
                                                >
                                                    {svc.needs_api_key ? "Clé requise" : "Accessible"}
                                                </span>
                                            </span>
                                        </button>
                                    </motion.li>
                                );
                            })}
                        </motion.ul>
                    </div>
                )
            )}

            <div className="flex flex-col-reverse gap-2 border-t border-white/[0.06] pt-5 sm:flex-row">
                <Button variant="ghost" onClick={onBack}>
                    <ChevronLeft /> Retour
                </Button>
                <Button onClick={onContinue} disabled={scanning} className="sm:ml-auto">
                    {count > 0 ? `Continuer avec ${plural(count, "service")}` : "Configurer à la main"}
                    <ArrowRight />
                </Button>
            </div>
        </div>
    );
}

/* ── Étape 3 : une ligne de service ─────────────────────────── */

function ServiceRow({
    index,
    row,
    errors,
    test,
    canRemove,
    onChange,
    onTypeChange,
    onRemove,
    onTest,
}: {
    index: number;
    row: Row;
    errors?: RowErrors;
    test?: { pending: boolean; result?: SetupTestResult };
    canRemove: boolean;
    onChange: <K extends keyof Row>(id: string, field: K, value: Row[K]) => void;
    onTypeChange: (id: string, type: string) => void;
    onRemove: (id: string) => void;
    onTest: (row: Row) => void;
}) {
    const hasErrors = !!errors && Object.keys(errors).length > 0;
    const id = (f: string) => `${row.id}-${f}`;
    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, x: -24, transition: { duration: 0.2 } }}
            transition={{ duration: 0.35, ease: EASE_OUT }}
            className={cn(
                "glass space-y-4 rounded-2xl p-4 transition-shadow",
                hasErrors && "shadow-[inset_0_0_0_1px_rgb(239_68_68/0.35)]",
            )}
        >
            <div className="flex items-center gap-3">
                <TypeIcon type={row.type} className="h-9 w-9" />
                <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{row.name || serviceVisual(row.type).label}</p>
                    <p className="text-[11px] text-muted-foreground">Service n°{index + 1}</p>
                </div>
                <Button size="sm" variant="outline" onClick={() => onTest(row)} disabled={test?.pending}>
                    {test?.pending ? <Loader2 className="animate-spin" /> : <Zap />}
                    Tester
                </Button>
                {canRemove && (
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className="text-muted-foreground hover:bg-red-500/10 hover:text-red-400"
                        onClick={() => onRemove(row.id)}
                        aria-label={`Retirer le service n°${index + 1}`}
                    >
                        <Trash2 />
                    </Button>
                )}
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <FormField id={id("type")} label="Application">
                    <Select value={row.type} onValueChange={(v) => onTypeChange(row.id, v)}>
                        <SelectTrigger id={id("type")}>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {SERVICE_TYPE_OPTIONS.map((t) => (
                                <SelectItem key={t.value} value={t.value}>
                                    {t.label} <span className="text-muted-foreground">· port {t.port}</span>
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </FormField>
                <FormField id={id("name")} label="Nom" error={errors?.name}>
                    <Input
                        id={id("name")}
                        value={row.name}
                        placeholder={`Mon ${serviceVisual(row.type).label}`}
                        onChange={(e) => {
                            onChange(row.id, "name", e.target.value);
                            onChange(row.id, "nameTouched", true);
                        }}
                        aria-invalid={!!errors?.name}
                    />
                </FormField>
                <FormField id={id("url")} label="Adresse" error={errors?.url}>
                    <Input
                        id={id("url")}
                        value={row.url}
                        placeholder={exampleUrl(row.type)}
                        inputMode="url"
                        spellCheck={false}
                        autoComplete="off"
                        className="font-mono text-sm"
                        onChange={(e) => onChange(row.id, "url", e.target.value)}
                        aria-invalid={!!errors?.url}
                    />
                </FormField>
                <FormField id={id("key")} label="Clé API" error={errors?.api_key} hint={API_KEY_HINTS[row.type as keyof typeof API_KEY_HINTS]}>
                    <SecretInput
                        id={id("key")}
                        icon={KeyRound}
                        value={row.api_key}
                        placeholder="Colle la clé ici"
                        onChange={(e) => onChange(row.id, "api_key", e.target.value)}
                        aria-invalid={!!errors?.api_key}
                    />
                </FormField>
            </div>

            <AnimatePresence initial={false}>
                {test?.result && (
                    <motion.p
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        aria-live="polite"
                        className={cn(
                            "flex items-start gap-2 overflow-hidden text-xs font-medium",
                            test.result.ok ? "text-emerald-400" : "text-red-400",
                        )}
                    >
                        {test.result.ok ? <CheckCircle2 className="mt-px h-3.5 w-3.5 shrink-0" /> : <XCircle className="mt-px h-3.5 w-3.5 shrink-0" />}
                        {test.result.label}
                    </motion.p>
                )}
            </AnimatePresence>
        </motion.div>
    );
}

/* ── Étape 4 : Terminé ──────────────────────────────────────── */

function DoneStep({ added, loggedIn, onOpen }: { added: number; loggedIn: boolean; onOpen: () => void }) {
    return (
        <div className="space-y-6 py-4 text-center">
            <div className="relative mx-auto h-24 w-24">
                {/* Éclats qui jaillissent autour de la coche */}
                {Array.from({ length: 12 }).map((_, i) => {
                    const angle = (i / 12) * Math.PI * 2;
                    return (
                        <motion.span
                            key={i}
                            aria-hidden
                            className={cn("absolute left-1/2 top-1/2 h-1.5 w-1.5 rounded-full", i % 2 ? "bg-brand" : "bg-primary")}
                            initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
                            animate={{ x: Math.cos(angle) * 70, y: Math.sin(angle) * 70, opacity: 0, scale: 0.4 }}
                            transition={{ duration: 1.1, ease: EASE_OUT, delay: 0.25 }}
                        />
                    );
                })}
                <motion.div
                    initial={{ scale: 0, rotate: -40 }}
                    animate={{ scale: 1, rotate: 0 }}
                    transition={{ type: "spring", stiffness: 260, damping: 16 }}
                    className="relative flex h-24 w-24 items-center justify-center rounded-full bg-gradient-to-br from-emerald-400/30 to-teal-500/10 ring-1 ring-emerald-400/40 shadow-[0_0_48px_-6px_rgb(52_211_153/0.7)]"
                >
                    <CheckCircle2 className="h-12 w-12 text-emerald-300" strokeWidth={1.6} />
                </motion.div>
            </div>
            <div>
                <h2 className="text-2xl font-bold tracking-tight sm:text-3xl">Tout est prêt !</h2>
                <p className="mt-2 text-muted-foreground">
                    {plural(added, "service ajouté", "services ajoutés")}. Ta flotte est prête à appareiller.
                </p>
            </div>
            {!loggedIn && (
                <p className="mx-auto max-w-sm rounded-xl border border-white/[0.06] bg-background/30 px-4 py-3 text-xs text-muted-foreground">
                    Connecte-toi avec ton mot de passe administrateur.
                </p>
            )}
            <Button onClick={onOpen} size="lg" className="w-full sm:w-auto sm:px-10">
                {loggedIn ? <LayoutDashboard /> : <LogIn />}
                {loggedIn ? "Ouvrir le tableau de bord" : "Se connecter"}
            </Button>
        </div>
    );
}
