"use client";

/**
 * Assistant d'installation (premier lancement, hors coquille applicative).
 * ----------------------------------------------------------------
 * Pensé pour quelqu'un qui n'est PAS informaticien : chaque étape dit ce
 * qu'on fait, pourquoi, et ce qui vient après. On est guidé jusqu'au bout,
 * y compris pour ce qu'aucun installeur ne peut faire à notre place
 * (ajouter des sources dans Prowlarr, renseigner un fournisseur Usenet…).
 *
 * 6 étapes :
 *   1. Bienvenue       — le plan de route, rien à faire ;
 *   2. Mot de passe    — créé ICI (plus de .env à éditer) ; l'API ouvre
 *                        la session dans la foulée ;
 *   3. Applications    — « Tout connecter » (lecture des configs +
 *                        câblage) en vedette ; scan réseau et saisie à la
 *                        main en repli pour une installation « maison » ;
 *   4. À faire         — liste VÉRIFIÉE auprès des applis, avec pour chaque
 *                        ligne le pourquoi, le quoi faire et un lien direct ;
 *   5. Équipement      — TV, tablette, ampli, caméras : tout est facultatif,
 *                        « je n'en ai pas » par défaut ;
 *   6. Terminé         — récapitulatif et prochaines étapes.
 *
 * Redirection : une instance DÉJÀ configurée à l'ouverture de la page part
 * vers le tableau de bord. Ce contrôle n'a lieu qu'au premier chargement :
 * sinon, dès les applications reliées (instance « configurée »), on serait
 * éjecté de l'assistant avant la liste « À faire » et l'équipement.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import {
    AlertCircle,
    ArrowRight,
    Check,
    CheckCircle2,
    ChevronDown,
    ChevronLeft,
    Clock,
    HeartHandshake,
    KeyRound,
    LayoutDashboard,
    Link2,
    ListChecks,
    Loader2,
    LockKeyhole,
    LogIn,
    PackageCheck,
    PencilLine,
    Plus,
    Radar,
    RefreshCw,
    Rocket,
    Search,
    Server,
    Sparkles,
    Trash2,
    XCircle,
    Zap,
    type LucideIcon,
} from "lucide-react";
import { CreatePasswordForm } from "@/components/auth/create-password-form";
import { StackWiring } from "@/components/stack/stack-wiring";
import { EquipmentPicker } from "@/components/setup/equipment-picker";
import { SetupChecklist } from "@/components/setup/setup-checklist";
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
import { useSetupChecklist } from "@/hooks/use-setup-checklist";
import { useModules } from "@/hooks/use-modules";
import { isAuthenticated, login } from "@/lib/api-client";
import { plural } from "@/lib/format";
import { EASE_OUT, SPRING, fadeUp, stagger } from "@/lib/motion";
import { cn } from "@/lib/utils";

/* ── Étapes ─────────────────────────────────────────────────── */

type StepId = "welcome" | "password" | "connect" | "manual" | "todo" | "equipment" | "done";

/** Étapes affichées dans la frise (la saisie manuelle fait partie de « Applications »). */
const STEPS: { id: StepId; title: string; icon: LucideIcon }[] = [
    { id: "welcome", title: "Bienvenue", icon: Sparkles },
    { id: "password", title: "Mot de passe", icon: LockKeyhole },
    { id: "connect", title: "Applications", icon: Link2 },
    { id: "todo", title: "À faire", icon: ListChecks },
    { id: "equipment", title: "Équipement", icon: PackageCheck },
    { id: "done", title: "Terminé", icon: Rocket },
];

/** Ordre de navigation (sert au sens de l'animation suivant / retour). */
const ORDER: StepId[] = ["welcome", "password", "connect", "manual", "todo", "equipment", "done"];

/** Position dans la frise : « manual » s'affiche comme « Applications ». */
const stepperIndex = (id: StepId) => STEPS.findIndex((s) => s.id === (id === "manual" ? "connect" : id));

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
    const [[step, direction], setStepState] = useState<[StepId, number]>(["welcome", 0]);
    const goTo = (next: StepId) =>
        setStepState(([cur]) => [next, ORDER.indexOf(next) > ORDER.indexOf(cur) ? 1 : -1]);

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
    // Session ouverte (mot de passe créé ou saisi) : relu après chaque étape
    const [loggedIn, setLoggedIn] = useState(false);
    useEffect(() => setLoggedIn(isAuthenticated()), [step]);

    // Instance déjà configurée À L'OUVERTURE → tableau de bord (ou connexion).
    // Une seule fois : ensuite, relier les applis rend l'instance
    // « configurée » et il ne faut surtout pas quitter l'assistant.
    const initialCheck = useRef(false);
    useEffect(() => {
        if (!status || initialCheck.current) return;
        initialCheck.current = true;
        if (status.is_configured) router.replace(isAuthenticated() ? "/dashboard" : "/login");
    }, [status, router]);

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

    /** Passe à la saisie manuelle en ajoutant les services cochés (sans doublon). */
    const continueToManual = () => {
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
        goTo("manual");
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

    /* ── Envoi de la saisie manuelle ────────────────────────── */
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
            await completeSetup(
                rows.map(({ name, type, url, api_key, is_enabled }) => ({
                    name: name.trim(),
                    type,
                    url: url.trim().replace(/\/+$/, ""),
                    api_key: api_key.trim(),
                    is_enabled,
                })),
            );
            void refetch();
            goTo("todo");
        } catch (e) {
            setSubmitError(e instanceof Error ? e.message : "La configuration a échoué.");
        } finally {
            setSubmitting(false);
        }
    };

    /* ── Rendu ──────────────────────────────────────────────── */
    return (
        <div className="relative min-h-screen overflow-x-hidden">
            <main className="mx-auto flex min-h-screen w-full max-w-3xl flex-col items-center px-4 pb-10 pt-8 sm:pt-12">
                <BrandMark />

                {isLoading ? (
                    <div className="mt-10 flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" /> Préparation de l&apos;équipage…
                    </div>
                ) : isError ? (
                    <div className="glass-strong mt-10 w-full max-w-md rounded-3xl p-6 text-center">
                        <AlertCircle className="mx-auto h-8 w-8 text-destructive" />
                        <p className="mt-3 font-semibold">ArrMada ne répond pas encore</p>
                        <p className="mt-1 text-sm text-muted-foreground">{error instanceof Error ? error.message : ""}</p>
                        <p className="mt-3 text-xs text-muted-foreground">
                            Juste après l&apos;installation, il lui faut parfois une minute pour démarrer.
                        </p>
                        <Button className="mt-5" onClick={() => refetch()} disabled={isFetching}>
                            <RefreshCw className={isFetching ? "animate-spin" : ""} /> Réessayer
                        </Button>
                    </div>
                ) : (
                    <>
                        <Stepper current={stepperIndex(step)} />
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
                                    {step === "welcome" && <WelcomeStep onStart={() => goTo("password")} />}

                                    {step === "password" && (
                                        <PasswordStep
                                            passwordSet={!!status?.password_set}
                                            loggedIn={loggedIn}
                                            onReady={() => {
                                                void refetch();
                                                setLoggedIn(true);
                                                goTo("connect");
                                            }}
                                            onBack={() => goTo("welcome")}
                                        />
                                    )}

                                    {step === "connect" && (
                                        <ConnectStep
                                            loggedIn={loggedIn}
                                            hasServices={!!status?.has_services}
                                            servicesCount={status?.services_count ?? 0}
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
                                            onImported={() => void refetch()}
                                            onManual={continueToManual}
                                            onBack={() => goTo("password")}
                                            onContinue={() => goTo("todo")}
                                        />
                                    )}

                                    {step === "manual" && (
                                        <div className="space-y-5">
                                            <StepTitle
                                                icon={PencilLine}
                                                title="Saisie à la main"
                                                description="Pour chaque application : son adresse et sa clé API. La clé se trouve dans l'appli, rubrique Settings › General (Sonarr, Radarr, Prowlarr) ou Config › General (SABnzbd)."
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
                                                <Plus /> Ajouter une application
                                            </Button>

                                            <div className="flex flex-wrap items-center gap-2 text-xs">
                                                <span className="chip">
                                                    <CheckCircle2 className="h-3 w-3 text-success" /> {plural(readyCount, "prête", "prêtes")}
                                                </span>
                                                {invalidCount > 0 && (
                                                    <span className="chip">
                                                        <AlertCircle className="h-3 w-3 text-warning" /> {plural(invalidCount, "incomplète", "incomplètes")}
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
                                                        className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive"
                                                    >
                                                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {submitError}
                                                    </motion.p>
                                                )}
                                            </AnimatePresence>

                                            <StepFooter onBack={() => goTo("connect")}>
                                                <Button onClick={handleComplete} disabled={submitting} size="lg" className="sm:ml-auto">
                                                    {submitting ? <Loader2 className="animate-spin" /> : <Check />}
                                                    {submitting ? "Enregistrement…" : "Enregistrer et continuer"}
                                                </Button>
                                            </StepFooter>
                                        </div>
                                    )}

                                    {step === "todo" && <TodoStep onBack={() => goTo("connect")} onContinue={() => goTo("equipment")} />}

                                    {step === "equipment" && (
                                        <EquipmentStep onBack={() => goTo("todo")} onContinue={() => goTo("done")} />
                                    )}

                                    {step === "done" && (
                                        <DoneStep
                                            servicesCount={status?.services_count ?? 0}
                                            onOpen={() => router.push(isAuthenticated() ? "/dashboard" : "/login")}
                                            onBack={() => goTo("equipment")}
                                        />
                                    )}
                                </motion.section>
                            </AnimatePresence>
                        </div>
                        <p className="mt-5 max-w-md text-balance text-center text-xs text-muted-foreground">
                            Tu peux fermer cette page à tout moment : ce qui est fait est enregistré. La liste « À faire »
                            et l&apos;équipement restent dans Paramètres › Mon équipement.
                        </p>
                    </>
                )}
            </main>
        </div>
    );
}

/* ── Logo ───────────────────────────────────────────────────── */

function BrandMark() {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 18 }}
            className="flex flex-col items-center gap-3"
        >
            <div className="border-beam relative h-16 w-16 rounded-2xl p-[2px] sm:h-20 sm:w-20">
                <div className="h-full w-full overflow-hidden rounded-[14px] sm:rounded-[18px]">
                    <BrandIcon title="ArrMada" />
                </div>
            </div>
            <p className="text-lg font-bold tracking-tight">
                Arr<span className="text-gradient">Mada</span>
            </p>
        </motion.div>
    );
}

/* ── Frise des étapes ───────────────────────────────────────── */

function Stepper({ current }: { current: number }) {
    return (
        <>
            <ol aria-label="Étapes de l'installation" className="mt-6 flex w-full max-w-2xl items-start">
                {STEPS.map((s, i) => {
                    const done = i < current;
                    const active = i === current;
                    const Icon = s.icon;
                    return (
                        <li key={s.id} className="flex flex-1 items-start last:flex-none" aria-current={active ? "step" : undefined}>
                            <div className="flex w-10 flex-col items-center gap-1.5 sm:w-20">
                                <motion.div
                                    initial={false}
                                    animate={{ scale: active ? 1.08 : 1 }}
                                    transition={SPRING}
                                    className={cn(
                                        "relative flex h-9 w-9 items-center justify-center rounded-full border transition-colors duration-300 sm:h-10 sm:w-10",
                                        done && "border-primary/60 bg-primary text-primary-foreground",
                                        active && "border-primary/60 bg-primary/15 text-primary",
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
                                {/* Libellés masqués sur téléphone (6 étapes ne tiennent pas) : affichés dessous */}
                                <span
                                    className={cn(
                                        "hidden text-center text-[11px] font-medium transition-colors sm:block",
                                        active ? "text-foreground" : done ? "text-primary" : "text-muted-foreground",
                                    )}
                                >
                                    {s.title}
                                </span>
                            </div>
                            {i < STEPS.length - 1 && (
                                <div aria-hidden className="relative mx-1 mt-[18px] h-0.5 flex-1 overflow-hidden rounded-full bg-white/10 sm:mt-5">
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
            <p className="mt-3 text-sm text-muted-foreground sm:hidden">
                Étape {current + 1} sur {STEPS.length} · <span className="font-medium text-foreground">{STEPS[current]?.title}</span>
            </p>
        </>
    );
}

/* ── Briques communes ───────────────────────────────────────── */

function StepTitle({ icon: Icon, title, description }: { icon: LucideIcon; title: string; description: React.ReactNode }) {
    return (
        <div className="flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/25">
                <Icon className="h-5 w-5" />
            </span>
            <div className="min-w-0">
                <h2 className="text-balance text-xl font-bold tracking-tight">{title}</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>
            </div>
        </div>
    );
}

/** Bas d'étape : « Retour » à gauche, action principale à droite. */
function StepFooter({ onBack, children }: { onBack?: () => void; children: React.ReactNode }) {
    return (
        <div className="flex flex-col-reverse gap-2 border-t border-white/[0.06] pt-5 sm:flex-row sm:items-center">
            {onBack && (
                <Button variant="ghost" onClick={onBack}>
                    <ChevronLeft /> Retour
                </Button>
            )}
            {children}
        </div>
    );
}

/** Encadré repliable « Pourquoi ? » / « Ça ne marche pas ? ». */
function Explain({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <details className="group rounded-2xl border border-white/[0.06] bg-white/[0.02] px-4 py-3 text-sm">
            <summary className="flex cursor-pointer select-none list-none items-center gap-2 font-medium text-muted-foreground group-open:text-foreground">
                <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                {title}
            </summary>
            <div className="mt-2 space-y-2 pl-6 text-muted-foreground">{children}</div>
        </details>
    );
}

/* ── 1. Bienvenue ───────────────────────────────────────────── */

const PLAN: { icon: LucideIcon; title: string; desc: string; time: string }[] = [
    { icon: LockKeyhole, title: "Choisir ton mot de passe", desc: "Il protège ArrMada.", time: "1 min" },
    { icon: Link2, title: "Relier tes applications", desc: "Un bouton : ArrMada branche tout ensemble.", time: "1 min" },
    { icon: ListChecks, title: "Finir ce qui reste", desc: "On te montre quoi faire, et où cliquer.", time: "5 à 10 min" },
    { icon: PackageCheck, title: "Dire ce que tu as", desc: "TV, tablette, ampli, caméras : tout est facultatif.", time: "1 min" },
];

function WelcomeStep({ onStart }: { onStart: () => void }) {
    return (
        <div className="space-y-7">
            <div className="text-center">
                <h1 className="text-balance text-3xl font-bold tracking-tight sm:text-4xl">
                    Bienvenue dans <span className="text-gradient-animated">ArrMada</span>
                </h1>
                <p className="mx-auto mt-2 max-w-md text-balance text-muted-foreground">
                    Tes applications sont installées. Cet assistant t&apos;accompagne jusqu&apos;au premier film,
                    étape par étape.
                </p>
            </div>

            <motion.ol variants={stagger(0.15, 0.07)} initial="hidden" animate="show" className="space-y-2">
                {PLAN.map((p, i) => (
                    <motion.li key={p.title} variants={fadeUp} className="flex items-center gap-3 rounded-2xl bg-white/[0.03] p-3.5">
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-sm font-bold text-primary">
                            {i + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold">{p.title}</p>
                            <p className="text-xs text-muted-foreground">{p.desc}</p>
                        </div>
                        <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="h-3 w-3" /> {p.time}
                        </span>
                    </motion.li>
                ))}
            </motion.ol>

            <p className="flex items-start gap-2.5 rounded-2xl border border-primary/20 bg-primary/[0.06] p-4 text-sm">
                <HeartHandshake className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <span>
                    Pas besoin d&apos;être informaticien. Quand un mot te semble obscur, ouvre la rubrique{" "}
                    <span className="font-semibold">« Pourquoi ? »</span> juste en dessous : elle l&apos;explique simplement.
                </span>
            </p>

            <div className="text-center">
                <Button onClick={onStart} size="lg" className="w-full sm:w-auto sm:px-10">
                    C&apos;est parti <ArrowRight />
                </Button>
            </div>
        </div>
    );
}

/* ── 2. Mot de passe ────────────────────────────────────────── */

function PasswordStep({
    passwordSet,
    loggedIn,
    onReady,
    onBack,
}: {
    passwordSet: boolean;
    loggedIn: boolean;
    /** Session ouverte : on passe à la suite. */
    onReady: () => void;
    onBack: () => void;
}) {
    return (
        <div className="space-y-5">
            <StepTitle
                icon={LockKeyhole}
                title={passwordSet ? "Mot de passe administrateur" : "Choisis ton mot de passe"}
                description="C'est la clé d'ArrMada : personne sans lui ne peut voir ni modifier ta médiathèque. Tu pourras le changer dans Paramètres."
            />

            {!passwordSet ? (
                <>
                    <CreatePasswordForm onCreated={onReady} submitLabel="Enregistrer et continuer" />
                    <Explain title="Un conseil pour ne pas l'oublier">
                        <p>
                            Note-le dans ton gestionnaire de mots de passe, ou sur papier rangé en lieu sûr. Une phrase de
                            plusieurs mots (« le chat dort sur le canapé ») est plus solide et plus facile à retenir
                            qu&apos;un mot compliqué.
                        </p>
                        <p>Oublié ? Il se réinitialise depuis le serveur avec la commande arrmada-cli (voir la documentation).</p>
                    </Explain>
                </>
            ) : loggedIn ? (
                <p className="flex items-start gap-2 rounded-xl border border-success/25 bg-success/10 px-3.5 py-2.5 text-sm text-success">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> Mot de passe en place et session ouverte.
                </p>
            ) : (
                <InlineLogin onLoggedIn={onReady} />
            )}

            <StepFooter onBack={onBack}>
                {passwordSet && loggedIn && (
                    <Button onClick={onReady} size="lg" className="sm:ml-auto">
                        Continuer <ArrowRight />
                    </Button>
                )}
            </StepFooter>
        </div>
    );
}

/**
 * Mot de passe déjà créé (on revient dans l'assistant après l'avoir fermé) :
 * connexion SUR PLACE. La page /login renverrait ici tant que l'instance
 * n'a aucune application reliée (boucle).
 */
function InlineLogin({ onLoggedIn }: { onLoggedIn: () => void }) {
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const submit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);
        try {
            await login(password);
            onLoggedIn();
        } catch {
            setError("Mot de passe incorrect.");
        } finally {
            setLoading(false);
        }
    };
    return (
        <form onSubmit={submit} className="space-y-3">
            <p className="text-sm text-muted-foreground">Tu as déjà choisi un mot de passe : saisis-le pour continuer.</p>
            <FormField id="setup-login" label="Mot de passe" error={error}>
                <SecretInput
                    id="setup-login"
                    icon={KeyRound}
                    value={password}
                    autoComplete="current-password"
                    onChange={(e) => setPassword(e.target.value)}
                    aria-invalid={!!error}
                />
            </FormField>
            <Button type="submit" disabled={loading || !password}>
                {loading ? <Loader2 className="animate-spin" /> : <LogIn />} Se connecter
            </Button>
        </form>
    );
}

/* ── 3. Applications ────────────────────────────────────────── */

function ConnectStep({
    loggedIn,
    hasServices,
    servicesCount,
    scanning,
    scanError,
    discovered,
    picked,
    keyOf,
    onScan,
    onToggle,
    onImported,
    onManual,
    onBack,
    onContinue,
}: {
    loggedIn: boolean;
    hasServices: boolean;
    servicesCount: number;
    scanning: boolean;
    scanError: string;
    discovered: DiscoveredService[] | null;
    picked: Set<string>;
    keyOf: (d: DiscoveredService) => string;
    onScan: () => void;
    onToggle: (key: string) => void;
    /** « Tout connecter » a tourné : relire l'état (services enregistrés). */
    onImported: () => void;
    onManual: () => void;
    onBack: () => void;
    onContinue: () => void;
}) {
    const count = discovered?.filter((d) => picked.has(keyOf(d))).length ?? 0;
    return (
        <div className="space-y-5">
            <StepTitle
                icon={Link2}
                title="Relier tes applications"
                description="ArrMada retrouve Sonarr (séries), Radarr (films), Prowlarr (sources), ton logiciel de téléchargement et Jellyfin, puis les branche entre eux. Tu n'as rien à recopier."
            />

            {loggedIn ? (
                <div className="space-y-3 rounded-2xl border border-primary/20 bg-primary/[0.04] p-4">
                    <p className="text-sm">
                        <span className="font-semibold">Vérifie la liste, puis clique sur « Tout connecter ».</span>{" "}
                        <span className="text-muted-foreground">Chaque branchement est testé avant d&apos;être enregistré, et relancer ne crée jamais de doublon.</span>
                    </p>
                    <StackWiring variant="wizard" onApplied={() => onImported()} />
                </div>
            ) : (
                <p className="rounded-xl border border-warning/25 bg-warning/10 px-3.5 py-2.5 text-sm text-warning">
                    Reviens à l&apos;étape Mot de passe pour ouvrir ta session : la connexion automatique en a besoin.
                </p>
            )}

            {hasServices && (
                <p className="flex items-start gap-2 rounded-xl border border-success/25 bg-success/10 px-3.5 py-2.5 text-sm text-success">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    {plural(servicesCount, "application reliée", "applications reliées")} à ArrMada. Tu peux continuer.
                </p>
            )}

            <Explain title="Pourquoi relier les applications ?">
                <p>
                    Chaque appli a un rôle : Prowlarr connaît les sources, Sonarr et Radarr choisissent quoi télécharger,
                    le logiciel de téléchargement récupère les fichiers, Jellyfin les affiche. Seules, elles ne se parlent
                    pas. ArrMada lit leurs « clés API » (des mots de passe entre applis) et fait les présentations.
                </p>
            </Explain>

            {/* Repli : installation « maison », applis sur une autre machine */}
            <details className="group rounded-2xl border border-white/[0.06] bg-white/[0.02] p-4 text-sm">
                <summary className="flex cursor-pointer select-none list-none items-center gap-2 font-medium text-muted-foreground group-open:text-foreground">
                    <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
                    Mes applications sont sur une autre machine / installées autrement
                </summary>
                <div className="mt-4 space-y-4">
                    <p className="text-muted-foreground">
                        ArrMada peut chercher Sonarr, Radarr, Prowlarr, SABnzbd… sur ton réseau. Tu ajouteras ensuite leur clé
                        API à la main.
                    </p>
                    <ScanBlock
                        scanning={scanning}
                        scanError={scanError}
                        discovered={discovered}
                        picked={picked}
                        keyOf={keyOf}
                        onScan={onScan}
                        onToggle={onToggle}
                    />
                    <Button variant="outline" onClick={onManual} disabled={scanning} className="w-full">
                        <PencilLine />
                        {count > 0 ? `Continuer avec ${plural(count, "application")}` : "Saisir mes applications à la main"}
                    </Button>
                </div>
            </details>

            <StepFooter onBack={onBack}>
                <div className="flex flex-col items-stretch gap-1 sm:ml-auto sm:items-end">
                    <Button onClick={onContinue} size="lg" disabled={!hasServices}>
                        Continuer <ArrowRight />
                    </Button>
                    {!hasServices && (
                        <span className="text-center text-xs text-muted-foreground sm:text-right">
                            Relie au moins Sonarr ou Radarr pour continuer.
                        </span>
                    )}
                </div>
            </StepFooter>
        </div>
    );
}

/** Scan réseau + liste des applications détectées (cochables). */
function ScanBlock({
    scanning,
    scanError,
    discovered,
    picked,
    keyOf,
    onScan,
    onToggle,
}: {
    scanning: boolean;
    scanError: string;
    discovered: DiscoveredService[] | null;
    picked: Set<string>;
    keyOf: (d: DiscoveredService) => string;
    onScan: () => void;
    onToggle: (key: string) => void;
}) {
    return (
        <div className="space-y-3">
            {scanning ? (
                <div className="flex items-center gap-2 rounded-xl bg-background/30 px-4 py-3 text-muted-foreground">
                    <Radar className="h-4 w-4 animate-pulse text-primary" /> Exploration du réseau local (une vingtaine de secondes)…
                </div>
            ) : (
                <Button onClick={onScan} variant="secondary" className="w-full">
                    {discovered ? <RefreshCw /> : <Zap />}
                    {discovered ? "Relancer la recherche" : "Chercher sur mon réseau"}
                </Button>
            )}

            {scanError && (
                <p role="alert" className="flex items-start gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-destructive">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /> {scanError}
                </p>
            )}

            {discovered &&
                !scanning &&
                (discovered.length === 0 ? (
                    <p className="rounded-xl bg-background/30 px-4 py-3 text-muted-foreground">
                        Rien trouvé automatiquement. Pas de souci : saisis-les à la main.
                    </p>
                ) : (
                    <ul className="space-y-2">
                        {discovered.map((svc) => {
                            const k = keyOf(svc);
                            const on = picked.has(k);
                            return (
                                <li key={k}>
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
                                        {svc.version && <span className="hidden font-mono text-[10px] text-muted-foreground sm:block">v{svc.version}</span>}
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                ))}
        </div>
    );
}

/* ── Saisie manuelle : une ligne d'application ────────────── */

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
                hasErrors && "",
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
                        className="text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
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
                            test.result.ok ? "text-success" : "text-destructive",
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

/* ── 4. À faire ─────────────────────────────────────────────── */

function TodoStep({ onBack, onContinue }: { onBack: () => void; onContinue: () => void }) {
    const { data } = useSetupChecklist();
    const remaining = data?.todo ?? 0;
    return (
        <div className="space-y-5">
            <StepTitle
                icon={ListChecks}
                title="Ce qu'il te reste à faire"
                description="ArrMada a vérifié chaque application. Il reste quelques réglages qu'aucun installeur ne peut faire à ta place : suis les lignes orange dans l'ordre."
            />
            <SetupChecklist />
            <Explain title="Comment ça marche ?">
                <p>
                    Le bouton de chaque ligne ouvre la bonne page de la bonne application dans un nouvel onglet. Fais le
                    réglage là-bas, reviens sur cet onglet : la liste se vérifie toute seule (ou clique sur « Vérifier à
                    nouveau »).
                </p>
                <p>Une ligne rouge veut dire que l&apos;application ne répond pas : vérifie qu&apos;elle tourne sur ton serveur.</p>
            </Explain>
            <StepFooter onBack={onBack}>
                <div className="flex flex-col items-stretch gap-1 sm:ml-auto sm:items-end">
                    <Button onClick={onContinue} size="lg" variant={remaining ? "secondary" : "default"}>
                        {remaining ? "Je finirai plus tard" : "Continuer"} <ArrowRight />
                    </Button>
                    {remaining > 0 && (
                        <span className="text-center text-xs text-muted-foreground sm:text-right">
                            La liste reste dans Paramètres › Mon équipement.
                        </span>
                    )}
                </div>
            </StepFooter>
        </div>
    );
}

/* ── 5. Équipement ──────────────────────────────────────────── */

function EquipmentStep({ onBack, onContinue }: { onBack: () => void; onContinue: () => void }) {
    return (
        <div className="space-y-5">
            <StepTitle
                icon={PackageCheck}
                title="Ton équipement"
                description="ArrMada sait piloter une TV, une tablette, un ampli et des caméras. Tout ça est facultatif : active seulement ce que tu possèdes."
            />
            <p className="flex items-start gap-2.5 rounded-2xl border border-success/25 bg-success/[0.07] p-4 text-sm">
                <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                <span>
                    <span className="font-semibold">Tu n&apos;as rien de tout ça ? Parfait.</span>{" "}
                    <span className="text-muted-foreground">
                        Laisse tout éteint : ArrMada cherche, télécharge et range déjà tes films et séries,
                        et les menus inutiles disparaissent.
                    </span>
                </span>
            </p>
            <EquipmentPicker showNextLinks={false} />
            <Explain title="Et si j'achète une TV ou un ampli plus tard ?">
                <p>
                    Reviens dans Paramètres › Mon équipement et active-le : ses menus et réglages réapparaissent. Une TV
                    appairée est d&apos;ailleurs reconnue toute seule.
                </p>
            </Explain>
            <StepFooter onBack={onBack}>
                <Button onClick={onContinue} size="lg" className="sm:ml-auto">
                    Continuer <ArrowRight />
                </Button>
            </StepFooter>
        </div>
    );
}

/* ── 6. Terminé ─────────────────────────────────────────────── */

function DoneStep({ servicesCount, onOpen, onBack }: { servicesCount: number; onOpen: () => void; onBack: () => void }) {
    const { data: checklist } = useSetupChecklist();
    const { data: modules } = useModules();
    const remaining = checklist?.todo ?? 0;

    // Prochaines étapes selon l'équipement déclaré
    const next: { icon: LucideIcon; text: string }[] = [];
    if (remaining > 0) next.push({ icon: ListChecks, text: `Terminer ${plural(remaining, "réglage")} : Paramètres › Mon équipement.` });
    next.push({ icon: Search, text: "Demander ton premier film : Rechercher, tape un titre, puis Ajouter." });
    if (modules?.tv.enabled) next.push({ icon: Server, text: "Installer l'appli sur ta TV puis l'appairer : Paramètres › Kodi." });
    if (modules?.tablet.enabled) next.push({ icon: Server, text: "Ouvrir la page /ecran sur la tablette puis l'appairer : Paramètres › Kodi." });
    if (modules?.amplifier.enabled) next.push({ icon: Server, text: "Ajouter ton ampli : Paramètres › Ampli Yamaha." });
    if (modules?.cameras.enabled) next.push({ icon: Server, text: "Brancher les caméras : Paramètres › Kodi › Caméras Eufy." });

    return (
        <div className="space-y-6 py-2">
            <div className="text-center">
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
                        className="relative flex h-24 w-24 items-center justify-center rounded-full bg-success/15 ring-1 ring-success/40"
                    >
                        <CheckCircle2 className="h-12 w-12 text-success" strokeWidth={1.6} />
                    </motion.div>
                </div>
                <h2 className="mt-5 text-2xl font-bold tracking-tight sm:text-3xl">C&apos;est installé !</h2>
                <p className="mt-2 text-muted-foreground">
                    {plural(servicesCount, "application reliée", "applications reliées")}
                    {remaining === 0 ? ", rien d'autre à régler." : `, ${plural(remaining, "réglage")} à finir quand tu veux.`}
                </p>
            </div>

            <div className="rounded-2xl bg-white/[0.03] p-4">
                <p className="eyebrow pb-2">Et maintenant ?</p>
                <ol className="space-y-2 text-sm">
                    {next.map((n, i) => (
                        <li key={n.text} className="flex items-start gap-2.5">
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/15 text-[11px] font-bold text-primary">
                                {i + 1}
                            </span>
                            <span>{n.text}</span>
                        </li>
                    ))}
                </ol>
            </div>

            <StepFooter onBack={onBack}>
                <Button onClick={onOpen} size="lg" className="sm:ml-auto">
                    <LayoutDashboard /> Ouvrir ArrMada
                </Button>
            </StepFooter>
        </div>
    );
}
