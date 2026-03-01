"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import {
    Skull,
    Radar,
    Loader2,
    CheckCircle2,
    Plus,
    Trash2,
    ChevronRight,
    ChevronLeft,
    Sparkles,
    Server,
    Network,
    Zap,
    Shield,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import {
    useSetupStatus,
    discoverServices,
    completeSetup,
    type DiscoveredService,
    type ServiceSetupItem,
} from "@/hooks/use-setup";
import { SERVICE_META } from "@/lib/constants";

const SERVICE_TYPES = [
    { value: "sonarr", label: "Sonarr", port: 8989 },
    { value: "radarr", label: "Radarr", port: 7878 },
    { value: "lidarr", label: "Lidarr", port: 8686 },
    { value: "readarr", label: "Readarr", port: 8787 },
    { value: "prowlarr", label: "Prowlarr", port: 9696 },
    { value: "bazarr", label: "Bazarr", port: 6767 },
    { value: "jellyfin", label: "Jellyfin", port: 8096 },
    { value: "sabnzbd", label: "SABnzbd", port: 8080 },
];

const STEPS = [
    { title: "Bienvenue", icon: Skull },
    { title: "Découverte", icon: Radar },
    { title: "Configuration", icon: Server },
    { title: "Terminé", icon: CheckCircle2 },
];

export default function SetupPage() {
    const router = useRouter();
    const { data: status, isLoading } = useSetupStatus();
    const [step, setStep] = useState(0);
    const [scanning, setScanning] = useState(false);
    const [discovered, setDiscovered] = useState<DiscoveredService[]>([]);
    const [services, setServices] = useState<ServiceSetupItem[]>([]);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");

    // Redirect if already configured
    useEffect(() => {
        if (status?.is_configured) {
            router.replace("/dashboard");
        }
    }, [status, router]);

    // ── Network scan ────────────────────────────────────────
    const handleScan = useCallback(async () => {
        setScanning(true);
        setError("");
        try {
            const results = await discoverServices();
            setDiscovered(results);

            // Auto-create service entries from discovered ones
            const autoServices: ServiceSetupItem[] = results.map((d) => ({
                name: d.name,
                type: d.type,
                url: d.url,
                api_key: "",
                is_enabled: true,
            }));
            setServices((prev) =>
                prev.length > 0 ? prev : autoServices
            );
        } catch {
            setError("Échec de la détection réseau");
        } finally {
            setScanning(false);
        }
    }, []);

    // ── Add manual service ──────────────────────────────────
    const addService = () => {
        setServices((prev) => [
            ...prev,
            { name: "", type: "sonarr", url: "", api_key: "", is_enabled: true },
        ]);
    };

    const removeService = (index: number) => {
        setServices((prev) => prev.filter((_, i) => i !== index));
    };

    const updateService = (index: number, field: string, value: any) => {
        setServices((prev) =>
            prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
        );
    };

    // ── Submit setup ────────────────────────────────────────
    const handleComplete = async () => {
        const valid = services.filter(
            (s) => s.name && s.url && s.api_key && s.type
        );
        if (valid.length === 0) {
            setError("Ajoutez au moins un service avec une clé API");
            return;
        }

        setSubmitting(true);
        setError("");
        try {
            await completeSetup(valid);
            setStep(3); // Success step
        } catch (e: any) {
            setError(e.message || "Erreur lors de la configuration");
        } finally {
            setSubmitting(false);
        }
    };

    if (isLoading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-background flex items-center justify-center px-4 py-8">
            <div className="w-full max-w-2xl space-y-6">
                {/* ── Progress bar ───────────────────────────── */}
                <div className="flex items-center justify-center gap-2">
                    {STEPS.map((s, i) => {
                        const Icon = s.icon;
                        const isActive = i === step;
                        const isDone = i < step;
                        return (
                            <div key={i} className="flex items-center gap-2">
                                <motion.div
                                    initial={false}
                                    animate={{
                                        scale: isActive ? 1.1 : 1,
                                        backgroundColor: isDone
                                            ? "hsl(var(--primary))"
                                            : isActive
                                                ? "hsl(var(--primary))"
                                                : "hsl(var(--muted))",
                                    }}
                                    className={cn(
                                        "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
                                        (isActive || isDone) ? "text-primary-foreground" : "text-muted-foreground"
                                    )}
                                >
                                    {isDone ? (
                                        <CheckCircle2 className="h-5 w-5" />
                                    ) : (
                                        <Icon className="h-5 w-5" />
                                    )}
                                </motion.div>
                                {i < STEPS.length - 1 && (
                                    <div
                                        className={cn(
                                            "h-0.5 w-8 rounded-full transition-colors",
                                            i < step ? "bg-primary" : "bg-muted"
                                        )}
                                    />
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* ── Step content ───────────────────────────── */}
                <AnimatePresence mode="wait">
                    <motion.div
                        key={step}
                        initial={{ opacity: 0, x: 30 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -30 }}
                        transition={{ duration: 0.25 }}
                    >
                        {/* STEP 0: Welcome */}
                        {step === 0 && (
                            <Card className="border-primary/20">
                                <CardHeader className="text-center space-y-4 pb-2">
                                    <motion.div
                                        initial={{ scale: 0 }}
                                        animate={{ scale: 1 }}
                                        transition={{ type: "spring", duration: 0.5 }}
                                        className="mx-auto flex h-20 w-20 items-center justify-center rounded-2xl bg-primary text-primary-foreground"
                                    >
                                        <Skull className="h-10 w-10" />
                                    </motion.div>
                                    <div>
                                        <CardTitle className="text-3xl font-bold tracking-tight">
                                            Bienvenue sur ArrMada
                                        </CardTitle>
                                        <p className="text-muted-foreground mt-2">
                                            L&apos;interface unifiée pour votre stack *arr
                                        </p>
                                    </div>
                                </CardHeader>
                                <CardContent className="space-y-6 pt-4">
                                    <div className="grid gap-3 sm:grid-cols-2">
                                        {[
                                            { icon: Network, label: "Détection automatique", desc: "Scanne votre réseau pour trouver vos services" },
                                            { icon: Server, label: "Tableau de bord unifié", desc: "Gérez tous vos services en un seul endroit" },
                                            { icon: Sparkles, label: "Recommandations IA", desc: "Suggestions basées sur vos goûts" },
                                            { icon: Shield, label: "Sécurisé", desc: "Clés API chiffrées, JWT, rate limiting" },
                                        ].map((feat) => (
                                            <div
                                                key={feat.label}
                                                className="flex items-start gap-3 p-3 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors"
                                            >
                                                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 shrink-0">
                                                    <feat.icon className="h-4 w-4 text-primary" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium">{feat.label}</p>
                                                    <p className="text-xs text-muted-foreground">{feat.desc}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>

                                    {status && (
                                        <div className="text-center">
                                            <Badge variant="outline" className="text-xs">
                                                Base de données : {status.database_type === "postgresql" ? "PostgreSQL" : "SQLite"}
                                            </Badge>
                                        </div>
                                    )}

                                    <Button
                                        onClick={() => setStep(1)}
                                        className="w-full h-11"
                                        size="lg"
                                    >
                                        Commencer la configuration
                                        <ChevronRight className="h-4 w-4 ml-2" />
                                    </Button>
                                </CardContent>
                            </Card>
                        )}

                        {/* STEP 1: Discovery */}
                        {step === 1 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Radar className="h-5 w-5 text-primary" />
                                        Découverte réseau
                                    </CardTitle>
                                    <p className="text-sm text-muted-foreground">
                                        ArrMada peut scanner votre réseau local pour détecter automatiquement
                                        vos services Sonarr, Radarr, Prowlarr, etc.
                                    </p>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <Button
                                        onClick={handleScan}
                                        disabled={scanning}
                                        variant="outline"
                                        className="w-full h-11"
                                    >
                                        {scanning ? (
                                            <>
                                                <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                                Scan en cours…
                                            </>
                                        ) : (
                                            <>
                                                <Zap className="h-4 w-4 mr-2" />
                                                {discovered.length > 0
                                                    ? "Relancer le scan"
                                                    : "Scanner le réseau"}
                                            </>
                                        )}
                                    </Button>

                                    {/* Discovered services */}
                                    {discovered.length > 0 && (
                                        <div className="space-y-2">
                                            <p className="text-sm font-medium">
                                                {discovered.length} service(s) détecté(s) :
                                            </p>
                                            {discovered.map((svc, i) => {
                                                const meta = SERVICE_META[svc.type as keyof typeof SERVICE_META];
                                                return (
                                                    <motion.div
                                                        key={`${svc.type}-${svc.url}`}
                                                        initial={{ opacity: 0, y: 10 }}
                                                        animate={{ opacity: 1, y: 0 }}
                                                        transition={{ delay: i * 0.1 }}
                                                        className="flex items-center justify-between p-3 rounded-lg bg-muted/30 border border-border/50"
                                                    >
                                                        <div className="flex items-center gap-3">
                                                            <div
                                                                className="h-2.5 w-2.5 rounded-full"
                                                                style={{ backgroundColor: meta?.color || "#888" }}
                                                            />
                                                            <div>
                                                                <p className="text-sm font-medium">{svc.name}</p>
                                                                <p className="text-xs text-muted-foreground font-mono">
                                                                    {svc.url}
                                                                </p>
                                                            </div>
                                                        </div>
                                                        <div className="flex items-center gap-2">
                                                            {svc.version && (
                                                                <Badge variant="outline" className="text-xs font-mono">
                                                                    v{svc.version}
                                                                </Badge>
                                                            )}
                                                            <Badge
                                                                variant={svc.needs_api_key ? "secondary" : "default"}
                                                                className="text-xs"
                                                            >
                                                                {svc.needs_api_key ? "Clé requise" : "Accessible"}
                                                            </Badge>
                                                        </div>
                                                    </motion.div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {scanning && discovered.length === 0 && (
                                        <div className="text-center py-8">
                                            <div className="relative mx-auto w-16 h-16">
                                                <motion.div
                                                    animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                                                    transition={{ repeat: Infinity, duration: 2 }}
                                                    className="absolute inset-0 rounded-full bg-primary/20"
                                                />
                                                <div className="absolute inset-0 flex items-center justify-center">
                                                    <Radar className="h-8 w-8 text-primary" />
                                                </div>
                                            </div>
                                            <p className="text-sm text-muted-foreground mt-4">
                                                Scan des ports 6767–9696 sur le réseau local…
                                            </p>
                                        </div>
                                    )}

                                    <Separator />

                                    <div className="flex gap-3">
                                        <Button
                                            variant="ghost"
                                            onClick={() => setStep(0)}
                                        >
                                            <ChevronLeft className="h-4 w-4 mr-1" />
                                            Retour
                                        </Button>
                                        <Button
                                            onClick={() => {
                                                if (services.length === 0) addService();
                                                setStep(2);
                                            }}
                                            className="flex-1"
                                        >
                                            {discovered.length > 0
                                                ? "Configurer les services"
                                                : "Configuration manuelle"}
                                            <ChevronRight className="h-4 w-4 ml-1" />
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* STEP 2: Configuration */}
                        {step === 2 && (
                            <Card>
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <Server className="h-5 w-5 text-primary" />
                                        Configuration des services
                                    </CardTitle>
                                    <p className="text-sm text-muted-foreground">
                                        Renseignez l&apos;URL et la clé API de chaque service.
                                        Vous pouvez trouver la clé API dans{" "}
                                        <span className="font-medium">Settings → General</span> de chaque
                                        application.
                                    </p>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {services.map((svc, i) => {
                                        const meta = SERVICE_META[svc.type as keyof typeof SERVICE_META];
                                        return (
                                            <motion.div
                                                key={i}
                                                initial={{ opacity: 0, y: 10 }}
                                                animate={{ opacity: 1, y: 0 }}
                                                className="p-4 rounded-lg border border-border/50 bg-muted/10 space-y-3"
                                            >
                                                <div className="flex items-center justify-between">
                                                    <div className="flex items-center gap-2">
                                                        <div
                                                            className="h-3 w-3 rounded-full"
                                                            style={{ backgroundColor: meta?.color || "#888" }}
                                                        />
                                                        <span className="text-sm font-medium">
                                                            Service {i + 1}
                                                        </span>
                                                    </div>
                                                    <Button
                                                        variant="ghost"
                                                        size="icon"
                                                        className="h-7 w-7 text-muted-foreground hover:text-destructive"
                                                        onClick={() => removeService(i)}
                                                    >
                                                        <Trash2 className="h-3.5 w-3.5" />
                                                    </Button>
                                                </div>

                                                <div className="grid gap-3 sm:grid-cols-2">
                                                    <div className="space-y-1.5">
                                                        <Label className="text-xs">Type</Label>
                                                        <Select
                                                            value={svc.type}
                                                            onValueChange={(v) =>
                                                                updateService(i, "type", v)
                                                            }
                                                        >
                                                            <SelectTrigger>
                                                                <SelectValue />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {SERVICE_TYPES.map((t) => (
                                                                    <SelectItem
                                                                        key={t.value}
                                                                        value={t.value}
                                                                    >
                                                                        {t.label} (:{t.port})
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>
                                                    <div className="space-y-1.5">
                                                        <Label className="text-xs">Nom</Label>
                                                        <Input
                                                            placeholder="Mon Sonarr"
                                                            value={svc.name}
                                                            onChange={(e) =>
                                                                updateService(i, "name", e.target.value)
                                                            }
                                                        />
                                                    </div>
                                                </div>

                                                <div className="space-y-1.5">
                                                    <Label className="text-xs">URL</Label>
                                                    <Input
                                                        placeholder="http://192.168.1.100:8989"
                                                        value={svc.url}
                                                        onChange={(e) =>
                                                            updateService(i, "url", e.target.value)
                                                        }
                                                        className="font-mono text-sm"
                                                    />
                                                </div>

                                                <div className="space-y-1.5">
                                                    <Label className="text-xs">Clé API</Label>
                                                    <Input
                                                        placeholder="abc123def456..."
                                                        value={svc.api_key}
                                                        onChange={(e) =>
                                                            updateService(i, "api_key", e.target.value)
                                                        }
                                                        className="font-mono text-sm"
                                                        type="password"
                                                    />
                                                </div>
                                            </motion.div>
                                        );
                                    })}

                                    <Button
                                        variant="outline"
                                        onClick={addService}
                                        className="w-full border-dashed"
                                    >
                                        <Plus className="h-4 w-4 mr-2" />
                                        Ajouter un service
                                    </Button>

                                    {error && (
                                        <p className="text-sm text-destructive text-center">
                                            {error}
                                        </p>
                                    )}

                                    <Separator />

                                    <div className="flex gap-3">
                                        <Button
                                            variant="ghost"
                                            onClick={() => setStep(1)}
                                        >
                                            <ChevronLeft className="h-4 w-4 mr-1" />
                                            Retour
                                        </Button>
                                        <Button
                                            onClick={handleComplete}
                                            disabled={submitting || services.length === 0}
                                            className="flex-1"
                                        >
                                            {submitting ? (
                                                <>
                                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                                    Configuration…
                                                </>
                                            ) : (
                                                <>
                                                    Terminer la configuration
                                                    <CheckCircle2 className="h-4 w-4 ml-2" />
                                                </>
                                            )}
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        )}

                        {/* STEP 3: Success */}
                        {step === 3 && (
                            <Card className="border-green-500/20">
                                <CardContent className="pt-8 pb-8 text-center space-y-6">
                                    <motion.div
                                        initial={{ scale: 0 }}
                                        animate={{ scale: 1 }}
                                        transition={{ type: "spring", duration: 0.6 }}
                                        className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-green-500/10"
                                    >
                                        <CheckCircle2 className="h-10 w-10 text-green-500" />
                                    </motion.div>
                                    <div>
                                        <h2 className="text-2xl font-bold tracking-tight">
                                            Configuration terminée !
                                        </h2>
                                        <p className="text-muted-foreground mt-2">
                                            ArrMada est prêt. Vos services ont été configurés avec succès.
                                        </p>
                                    </div>
                                    <Button
                                        onClick={() => router.push("/login")}
                                        size="lg"
                                        className="h-11"
                                    >
                                        <Skull className="h-4 w-4 mr-2" />
                                        Aller au tableau de bord
                                    </Button>
                                </CardContent>
                            </Card>
                        )}
                    </motion.div>
                </AnimatePresence>
            </div>
        </div>
    );
}
