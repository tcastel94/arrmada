"use client";

/**
 * Boîte « Ajouter / Modifier un service *arr ».
 * ----------------------------------------------------------------
 * Corrections par rapport à l'ancienne version :
 *  - BUG : l'état du formulaire était initialisé UNE seule fois (au premier
 *    rendu) → en cliquant « Modifier » sur un autre service, les champs
 *    restaient vides ou affichaient l'ancien service. Le formulaire est
 *    maintenant un composant séparé, re-créé à chaque ouverture (`key`).
 *  - « Tester » AVANT d'enregistrer (URL + clé vérifiées par le backend).
 *  - Le port de l'URL suit le type choisi (8989 → 7878…).
 *  - Erreurs affichées (toast + message sous le champ), plus de console.
 *  - La boîte gère elle-même ses enregistrements : la page n'a qu'à l'ouvrir.
 */
import { useState, type FormEvent } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, KeyRound, Loader2, Plus, Save, Wand2, XCircle, Zap } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { FormField, SecretInput, validateHttpUrl } from "@/components/settings/form-field";
import { cn } from "@/lib/utils";
import { SPRING } from "@/lib/motion";
import type { ServiceType } from "@/types";
import type { ArrService, TestConnectionResult } from "@/types/service";
import { useCreateService, useTestServiceDraft, useUpdateService } from "@/hooks/use-services";
import {
    API_KEY_HINTS,
    SERVICE_TYPE_OPTIONS,
    exampleUrl,
    serviceVisual,
    swapDefaultPort,
} from "@/components/services/service-meta";

interface ServiceConfigDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    /** Service à modifier ; null/undefined = ajout. */
    service?: ArrService | null;
    /** Type présélectionné à l'ajout (ex: depuis un raccourci). */
    defaultType?: ServiceType;
}

export function ServiceConfigDialog({ open, onOpenChange, service, defaultType }: ServiceConfigDialogProps) {
    // On « fige » le service et un numéro de session À L'OUVERTURE :
    //  - le formulaire est recréé à chaque ouverture (key = session) → plus
    //    de champs vides ou périmés (bug de l'ancienne version) ;
    //  - pendant l'animation de fermeture, le titre et les champs restent
    //    affichés (la page remet `service` à null dès la fermeture).
    // Mise à jour d'état pendant le rendu = motif React officiel pour
    // dériver un état d'une prop (pas d'effet, donc pas de flash).
    const [prevOpen, setPrevOpen] = useState(open);
    const [session, setSession] = useState(0);
    const [frozen, setFrozen] = useState<ArrService | null>(service ?? null);
    if (open !== prevOpen) {
        setPrevOpen(open);
        if (open) {
            setFrozen(service ?? null);
            setSession((n) => n + 1);
        }
    }

    const isEditing = !!frozen;
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-xl">
                <DialogHeader>
                    <DialogTitle>{isEditing ? `Modifier ${frozen?.name}` : "Ajouter un service"}</DialogTitle>
                    <DialogDescription>
                        {isEditing
                            ? "Change l'adresse, la clé ou le nom. Laisse la clé vide pour conserver l'actuelle."
                            : "Connecte une application *arr à ArrMada. Teste la connexion avant d'enregistrer."}
                    </DialogDescription>
                </DialogHeader>
                <ServiceForm key={session} service={frozen} defaultType={defaultType} onDone={() => onOpenChange(false)} />
            </DialogContent>
        </Dialog>
    );
}

function ServiceForm({
    service,
    defaultType,
    onDone,
}: {
    service: ArrService | null;
    defaultType?: ServiceType;
    onDone: () => void;
}) {
    const isEditing = !!service;
    const create = useCreateService();
    const update = useUpdateService();
    const test = useTestServiceDraft();

    // État initialisé depuis le service à CHAQUE montage (cf. `key` du parent).
    const [type, setType] = useState<ServiceType>(service?.type ?? defaultType ?? "sonarr");
    const [name, setName] = useState(service?.name ?? serviceVisual(defaultType ?? "sonarr").label);
    // Tant que l'utilisateur n'a pas tapé de nom, le nom suit le type choisi.
    const [nameTouched, setNameTouched] = useState(isEditing);
    const [url, setUrl] = useState(service?.url ?? "");
    const [apiKey, setApiKey] = useState("");
    const [isEnabled, setIsEnabled] = useState(service?.is_enabled ?? true);
    const [submitted, setSubmitted] = useState(false);
    const [testResult, setTestResult] = useState<TestConnectionResult | null>(null);

    const visual = serviceVisual(type);
    const errors = {
        name: !name.trim() ? "Donne un nom à ce service." : null,
        url: validateHttpUrl(url, "http://192.168.1.10:8989"),
        apiKey: !isEditing && !apiKey.trim() ? (type === "deluge" ? "Le mot de passe est obligatoire." : "La clé API est obligatoire.") : null,
    };
    const hasErrors = Object.values(errors).some(Boolean);
    const saving = create.isPending || update.isPending;

    const changeType = (next: ServiceType) => {
        setUrl((u) => swapDefaultPort(u, type, next));
        if (!nameTouched) setName(serviceVisual(next).label);
        setType(next);
        setTestResult(null);
    };

    const runTest = () => {
        const err = validateHttpUrl(url, "http://192.168.1.10:8989");
        if (err) {
            setSubmitted(true);
            return;
        }
        setTestResult(null);
        test.mutate(
            { type, url: url.trim(), api_key: apiKey.trim() || undefined, service_id: service?.id },
            {
                onSuccess: (r) => setTestResult(r),
                onError: (e) =>
                    setTestResult({
                        success: false,
                        status: "offline",
                        latency_ms: null,
                        version: null,
                        // 404/405 : backend trop ancien (route /api/services/test absente).
                        error: /HTTP 40[45]|Not Found|Method Not Allowed/i.test(e.message)
                            ? "test avant enregistrement indisponible sur ce backend (enregistre, puis « Tester » sur la carte)."
                            : e.message,
                    }),
            },
        );
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setSubmitted(true);
        if (hasErrors) return;
        try {
            if (isEditing && service) {
                await update.mutateAsync({
                    id: service.id,
                    data: {
                        name: name.trim(),
                        url: url.trim(),
                        api_key: apiKey.trim() || undefined,
                        is_enabled: isEnabled,
                    },
                });
                toast.success("Modifications enregistrées", { description: name.trim() });
            } else {
                await create.mutateAsync({
                    name: name.trim(),
                    type,
                    url: url.trim(),
                    api_key: apiKey.trim(),
                    is_enabled: isEnabled,
                });
                toast.success(`${name.trim()} ajouté`, {
                    description: "Le premier contrôle de santé arrive dans la minute.",
                });
            }
            onDone();
        } catch (err) {
            toast.error("Impossible d'enregistrer", {
                description: err instanceof Error ? err.message : "Erreur inconnue",
            });
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Choix du type : tuiles aux couleurs de chaque application */}
            <fieldset className="space-y-2">
                <legend className="mb-2 text-xs font-medium text-muted-foreground">Application</legend>
                {isEditing ? (
                    <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-background/40 p-3">
                        <TypeIcon type={type} />
                        <div>
                            <p className="text-sm font-semibold">{visual.label}</p>
                            <p className="text-xs text-muted-foreground">Le type ne peut pas changer : supprime et recrée le service si besoin.</p>
                        </div>
                    </div>
                ) : (
                    <div role="radiogroup" aria-label="Type de service" className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        {SERVICE_TYPE_OPTIONS.map((opt) => {
                            const active = opt.value === type;
                            const Icon = opt.icon;
                            return (
                                <button
                                    key={opt.value}
                                    type="button"
                                    role="radio"
                                    aria-checked={active}
                                    onClick={() => changeType(opt.value)}
                                    className={cn(
                                        "relative flex items-center gap-2 rounded-xl border px-2.5 py-2 text-left text-xs font-medium transition-colors",
                                        active
                                            ? "border-transparent text-foreground"
                                            : "border-white/[0.06] bg-background/30 text-muted-foreground hover:border-white/[0.14] hover:text-foreground",
                                    )}
                                >
                                    {active && (
                                        <motion.span
                                            layoutId="service-type-pill"
                                            transition={SPRING}
                                            className="absolute inset-0 rounded-xl"
                                            style={{
                                                background: `${opt.color}1f`,
                                                boxShadow: `inset 0 0 0 1px ${opt.color}66, 0 0 22px -8px ${opt.color}`,
                                            }}
                                        />
                                    )}
                                    <Icon className="relative h-3.5 w-3.5 shrink-0" style={{ color: opt.color }} />
                                    <span className="relative truncate">{opt.label}</span>
                                </button>
                            );
                        })}
                    </div>
                )}
            </fieldset>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <FormField id="service-name" label="Nom" error={submitted ? errors.name : null}>
                    <Input
                        id="service-name"
                        placeholder={`Mon ${visual.label}`}
                        value={name}
                        onChange={(e) => {
                            setName(e.target.value);
                            setNameTouched(true);
                        }}
                        aria-invalid={submitted && !!errors.name}
                    />
                </FormField>
                <FormField id="service-url" label="URL" error={submitted ? errors.url : null}>
                    <Input
                        id="service-url"
                        inputMode="url"
                        autoComplete="off"
                        spellCheck={false}
                        placeholder={exampleUrl(type)}
                        value={url}
                        onChange={(e) => {
                            setUrl(e.target.value);
                            setTestResult(null);
                        }}
                        className="font-mono text-sm"
                        aria-invalid={submitted && !!errors.url}
                    />
                </FormField>
            </div>

            <FormField
                id="service-api-key"
                label={type === "deluge" ? "Mot de passe de l'interface web" : "Clé API"}
                hint={isEditing ? "Laisse vide pour conserver la clé actuelle." : API_KEY_HINTS[type]}
                error={submitted ? errors.apiKey : null}
            >
                <SecretInput
                    id="service-api-key"
                    icon={KeyRound}
                    placeholder={isEditing ? "•••••••• (inchangée)" : "Colle la clé ici"}
                    value={apiKey}
                    onChange={(e) => {
                        setApiKey(e.target.value);
                        setTestResult(null);
                    }}
                    aria-invalid={submitted && !!errors.apiKey}
                />
            </FormField>

            <div className="flex items-center justify-between gap-4 rounded-xl border border-white/[0.06] bg-background/30 px-3.5 py-3">
                <div>
                    <Label htmlFor="service-enabled" className="text-sm">
                        Service actif
                    </Label>
                    <p className="text-xs text-muted-foreground">Désactivé, il est ignoré par les contrôles et les synchronisations.</p>
                </div>
                <Switch id="service-enabled" checked={isEnabled} onCheckedChange={setIsEnabled} />
            </div>

            {/* Résultat du test : apparaît / disparaît en douceur */}
            <AnimatePresence initial={false}>
                {(test.isPending || testResult) && (
                    <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: "auto" }}
                        exit={{ opacity: 0, height: 0 }}
                        className="overflow-hidden"
                        aria-live="polite"
                    >
                        <TestBanner
                            pending={test.isPending}
                            result={testResult}
                            label={visual.label}
                            onUseUrl={(next) => {
                                setUrl(next);
                                setTestResult(null);
                            }}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            <div className="flex flex-col-reverse gap-2 pt-1 sm:flex-row sm:items-center">
                <Button type="button" variant="outline" onClick={runTest} disabled={test.isPending || saving}>
                    {test.isPending ? <Loader2 className="animate-spin" /> : <Zap />}
                    Tester
                </Button>
                <div className="flex-1" />
                <Button type="button" variant="ghost" onClick={onDone} disabled={saving}>
                    Annuler
                </Button>
                <Button type="submit" disabled={saving}>
                    {saving ? <Loader2 className="animate-spin" /> : isEditing ? <Save /> : <Plus />}
                    {isEditing ? "Enregistrer" : "Ajouter"}
                </Button>
            </div>
        </form>
    );
}

/** Pastille d'icône aux couleurs d'une application. */
export function TypeIcon({ type, className }: { type: string; className?: string }) {
    const v = serviceVisual(type);
    const Icon = v.icon;
    return (
        <span
            className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ring-1", className)}
            style={{
                background: `linear-gradient(135deg, ${v.color}33, ${v.color}0d)`,
                boxShadow: `0 0 24px -8px ${v.color}`,
                // ring-color via variable CSS : couleur propre à l'application
                ["--tw-ring-color" as string]: `${v.color}40`,
            }}
        >
            <Icon className="h-5 w-5" style={{ color: v.color }} />
        </span>
    );
}

/** Bandeau de résultat de test (en cours / succès / échec). */
function TestBanner({
    pending,
    result,
    label,
    onUseUrl,
}: {
    pending: boolean;
    result: TestConnectionResult | null;
    label: string;
    /** Remplit le champ URL avec l'adresse proposée (nom Docker qui répond). */
    onUseUrl: (url: string) => void;
}) {
    if (pending) {
        return (
            <div className="flex items-center gap-2.5 rounded-xl border border-primary/25 bg-primary/10 px-3.5 py-2.5 text-sm text-primary">
                <Loader2 className="h-4 w-4 animate-spin" />
                Connexion à {label}…
            </div>
        );
    }
    if (!result) return null;
    if (result.success) {
        const r = result;
        return (
            <div className="flex items-center gap-2.5 rounded-xl border border-success/25 bg-success/10 px-3.5 py-2.5 text-sm text-success">
                <CheckCircle2 className="h-4 w-4 shrink-0" />
                <span>
                    {label} répond
                    {r.latency_ms != null && <span className="tabular-nums"> en {r.latency_ms} ms</span>}
                    {r.version && <span className="font-mono text-success/80"> · v{r.version}</span>}
                </span>
            </div>
        );
    }
    return (
        <div className="flex flex-col gap-2 rounded-xl border border-destructive/25 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive">
            <div className="flex items-start gap-2.5">
                <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                {/* Le diagnostic (en français, avec la cause) passe avant l'erreur brute */}
                <span className="min-w-0 break-words">
                    Échec de la connexion
                    {result.diagnosis ? ` : ${result.diagnosis}` : result.error ? ` : ${result.error}` : "."}
                </span>
            </div>
            {result.suggested_url && (
                <div className="flex flex-wrap items-center gap-2 pl-[26px] text-xs">
                    <span>
                        {label} répond sur <span className="font-mono">{result.suggested_url}</span>.
                    </span>
                    <Button type="button" size="sm" variant="outline" onClick={() => onUseUrl(result.suggested_url!)}>
                        <Wand2 />
                        Utiliser cette adresse
                    </Button>
                </div>
            )}
        </div>
    );
}
