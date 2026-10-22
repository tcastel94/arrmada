"use client";

/**
 * Ligne « appareil » commune aux réglages Kodi, Yamaha et Cast.
 * ----------------------------------------------------------------
 * Avant : Kodi et Yamaha avaient chacun leur `InstanceRow` copié-collé,
 * avec suppression sans confirmation et résultat de test minuscule.
 * Ici : un seul composant —
 *  - pastille d'état (vérifiée automatiquement à l'affichage si `autoTest`),
 *  - bouton « Tester » visible avec son propre chargement,
 *  - « Modifier » (optionnel) et « Supprimer » avec boîte de confirmation,
 *  - mise en page empilée sur mobile, en ligne sur desktop.
 */
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, Pencil, Trash2, XCircle, Zap, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { StatusDot } from "@/components/fx/status-dot";
import { slideIn } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Teintes disponibles pour la tuile d'icône (une par famille d'appareil). */
const TONES = {
    violet: "from-violet-500/30 to-fuchsia-500/10 text-violet-300 ring-violet-400/25 shadow-violet-500/60",
    orange: "from-orange-500/30 to-amber-500/10 text-orange-300 ring-orange-400/25 shadow-orange-500/60",
    sky: "from-sky-500/30 to-cyan-500/10 text-sky-300 ring-sky-400/25 shadow-sky-500/60",
    slate: "from-slate-400/25 to-slate-500/10 text-slate-300 ring-slate-400/25",
} as const;

export interface DeviceTestResult {
    ok: boolean;
    label: string;
}

interface DeviceRowProps {
    icon: LucideIcon;
    tone?: keyof typeof TONES;
    name: string;
    /** Adresse affichée en police mono (URL, IP…). */
    address?: string;
    /** Détails secondaires (utilisateur, modèle…). */
    meta?: ReactNode;
    /** Badges à droite du nom (ex: « Désactivé », « Vidéo »). */
    badges?: ReactNode;
    /** Lance un test de connexion ; absent = pas de bouton Tester. */
    onTest?: () => Promise<DeviceTestResult>;
    /** Teste automatiquement à l'affichage (pastille d'état en direct). */
    autoTest?: boolean;
    onEdit?: () => void;
    /** Suppression (après confirmation). Doit lever une erreur en cas d'échec. */
    onDelete?: () => Promise<unknown>;
    deleteTitle?: string;
    deleteDescription?: ReactNode;
    /** Action supplémentaire (bouton) avant Modifier / Supprimer. */
    extraAction?: ReactNode;
}

export function DeviceRow({
    icon: Icon,
    tone = "slate",
    name,
    address,
    meta,
    badges,
    onTest,
    autoTest = false,
    onEdit,
    onDelete,
    deleteTitle,
    deleteDescription,
    extraAction,
}: DeviceRowProps) {
    const [result, setResult] = useState<DeviceTestResult | null>(null);
    const [testing, setTesting] = useState(false);
    const [confirmOpen, setConfirmOpen] = useState(false);

    // On garde la dernière fonction de test dans une ref : le test automatique
    // ne doit partir qu'UNE fois au montage, même si le parent se re-rend.
    const testRef = useRef(onTest);
    testRef.current = onTest;

    const runTest = useCallback(async (silent = false) => {
        if (!testRef.current) return;
        setTesting(true);
        try {
            const r = await testRef.current();
            setResult(r);
            if (!silent) (r.ok ? toast.success : toast.error)(`${name} : ${r.ok ? "connexion OK" : "injoignable"}`, { description: r.label });
        } catch (e) {
            const label = e instanceof Error ? e.message : "Erreur inconnue";
            setResult({ ok: false, label });
            if (!silent) toast.error(`Test de ${name} impossible`, { description: label });
        } finally {
            setTesting(false);
        }
    }, [name]);

    useEffect(() => {
        if (autoTest) void runTest(true);
        // Volontairement au montage uniquement (voir testRef).
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const dotTone = testing && !result ? "primary" : result ? (result.ok ? "online" : "offline") : "unknown";

    return (
        <motion.div
            layout
            variants={slideIn}
            exit={{ opacity: 0, x: 20, transition: { duration: 0.2 } }}
            className="glass glass-hover group relative flex flex-col gap-3 rounded-2xl p-3.5 sm:flex-row sm:items-center"
        >
            <div className="flex min-w-0 flex-1 items-center gap-3">
                <div className="relative shrink-0">
                    <div className={cn("flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ring-1", TONES[tone])}>
                        <Icon className="h-5 w-5" strokeWidth={1.8} />
                    </div>
                    {onTest && (
                        <span className="absolute -bottom-0.5 -right-0.5 rounded-full bg-background p-[3px]">
                            <StatusDot tone={dotTone} size="sm" pulse={dotTone === "online" || dotTone === "primary"} />
                        </span>
                    )}
                </div>
                <div className="min-w-0 flex-1">
                    <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                        <p className="truncate text-sm font-semibold">{name}</p>
                        {badges}
                    </div>
                    {address && <p className="truncate font-mono text-xs text-muted-foreground" title={address}>{address}</p>}
                    {meta && <div className="mt-0.5 text-[11px] text-muted-foreground">{meta}</div>}
                    <AnimatePresence initial={false}>
                        {result && (
                            <motion.p
                                key={`${result.ok}-${result.label}`}
                                initial={{ opacity: 0, y: -4 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0 }}
                                className={cn(
                                    "mt-1 flex items-center gap-1 text-[11px] font-medium",
                                    result.ok ? "text-emerald-400" : "text-red-400",
                                )}
                                aria-live="polite"
                            >
                                {result.ok ? <CheckCircle2 className="h-3 w-3 shrink-0" /> : <XCircle className="h-3 w-3 shrink-0" />}
                                <span className="truncate">{result.label}</span>
                            </motion.p>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            <div className="flex shrink-0 items-center gap-1.5 self-end sm:self-auto">
                {extraAction}
                {onTest && (
                    <Button size="sm" variant="outline" onClick={() => runTest(false)} disabled={testing}>
                        {testing ? <Loader2 className="animate-spin" /> : <Zap />}
                        Tester
                    </Button>
                )}
                {onEdit && (
                    <Button size="icon-sm" variant="ghost" onClick={onEdit} aria-label={`Modifier ${name}`}>
                        <Pencil />
                    </Button>
                )}
                {onDelete && (
                    <Button
                        size="icon-sm"
                        variant="ghost"
                        className="text-muted-foreground hover:bg-red-500/10 hover:text-red-400"
                        onClick={() => setConfirmOpen(true)}
                        aria-label={`Supprimer ${name}`}
                    >
                        <Trash2 />
                    </Button>
                )}
            </div>

            {onDelete && (
                <ConfirmDialog
                    open={confirmOpen}
                    onOpenChange={setConfirmOpen}
                    destructive
                    title={deleteTitle ?? `Supprimer ${name} ?`}
                    description={deleteDescription}
                    confirmLabel="Supprimer"
                    onConfirm={async () => {
                        try {
                            await onDelete();
                            toast.success(`${name} supprimé`);
                        } catch (e) {
                            toast.error("Suppression impossible", { description: e instanceof Error ? e.message : undefined });
                            throw e; // garde la boîte ouverte
                        }
                    }}
                />
            )}
        </motion.div>
    );
}
