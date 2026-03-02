"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
    Monitor,
    Volume2,
    Languages,
    Gauge,
    Tv,
    Loader2,
    CheckCircle,
    ArrowRight,
    ArrowLeft,
    RefreshCw,
    Zap,
    Shield,
    Sparkles,
    Eye,
} from "lucide-react";
import {
    useTrashStatus,
    useTrashSync,
    useTrashRecommend,
    useTrashApply,
    type MediaPreferences,
    type RecommendedProfile,
    type ApplyResult,
} from "@/hooks/use-trash-guides";
import { useServices } from "@/hooks/use-services";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";

// ── Step definitions ─────────────────────────────────────────

const STEPS = [
    { id: "display", title: "Écran", icon: Monitor },
    { id: "audio", title: "Audio", icon: Volume2 },
    { id: "language", title: "Langue", icon: Languages },
    { id: "quality", title: "Qualité", icon: Gauge },
    { id: "content", title: "Contenu", icon: Tv },
    { id: "review", title: "Résumé", icon: Eye },
];

// ── Option cards data ────────────────────────────────────────

const DISPLAY_OPTIONS = [
    {
        value: "sdr",
        label: "SDR",
        desc: "Écran standard sans HDR",
        emoji: "🖥️",
    },
    {
        value: "hdr10",
        label: "HDR10",
        desc: "HDR standard — la plupart des TV 4K",
        emoji: "🌅",
    },
    {
        value: "hdr10plus",
        label: "HDR10+",
        desc: "HDR dynamique Samsung",
        emoji: "✨",
    },
    {
        value: "dolby_vision",
        label: "Dolby Vision",
        desc: "HDR premium — LG OLED, Apple TV",
        emoji: "🎬",
    },
    {
        value: "dv_hdr10_fallback",
        label: "DV + HDR10 Fallback",
        desc: "Dolby Vision avec fallback HDR10 sur appareils non-DV",
        emoji: "🏆",
    },
];

const AUDIO_OPTIONS = [
    {
        value: "stereo",
        label: "Stéréo",
        desc: "TV, casque, enceintes 2.0",
        emoji: "🎧",
    },
    {
        value: "surround_51",
        label: "5.1 Surround",
        desc: "Home cinema classique",
        emoji: "🔊",
    },
    {
        value: "surround_71",
        label: "7.1 Surround",
        desc: "Home cinema avancé",
        emoji: "🎵",
    },
    {
        value: "atmos",
        label: "Dolby Atmos",
        desc: "Son immersif / barre de son Atmos",
        emoji: "🎭",
    },
];

const LANGUAGE_OPTIONS = [
    {
        value: "vo",
        label: "VO",
        desc: "Version originale uniquement",
        emoji: "🇬🇧",
    },
    {
        value: "vf",
        label: "VF",
        desc: "Version française uniquement",
        emoji: "🇫🇷",
    },
    {
        value: "multi",
        label: "Multi",
        desc: "Français + langue originale (meilleur choix)",
        emoji: "🌍",
    },
    {
        value: "vostfr",
        label: "VOSTFR",
        desc: "VO avec sous-titres français",
        emoji: "📝",
    },
];

const QUALITY_OPTIONS = [
    {
        value: "720p",
        label: "720p",
        desc: "Léger — pour connexions limitées",
        emoji: "📱",
    },
    {
        value: "1080p",
        label: "1080p",
        desc: "Full HD — le standard",
        emoji: "🖥️",
    },
    {
        value: "2160p",
        label: "4K",
        desc: "Ultra HD — la meilleure qualité",
        emoji: "📺",
    },
    {
        value: "best",
        label: "Meilleure dispo",
        desc: "Télécharge la meilleure qualité disponible",
        emoji: "💎",
    },
];

// ── OptionCard component ─────────────────────────────────────

function OptionCard({
    option,
    selected,
    onClick,
}: {
    option: { value: string; label: string; desc: string; emoji: string };
    selected: boolean;
    onClick: () => void;
}) {
    return (
        <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onClick}
            className={cn(
                "relative flex flex-col items-center gap-3 p-5 rounded-xl border-2 transition-all duration-200 text-left w-full",
                selected
                    ? "border-primary bg-primary/10 shadow-lg shadow-primary/10"
                    : "border-border bg-card hover:border-primary/40 hover:bg-card/80"
            )}
        >
            {selected && (
                <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    className="absolute top-2 right-2"
                >
                    <CheckCircle className="h-5 w-5 text-primary" />
                </motion.div>
            )}
            <span className="text-3xl">{option.emoji}</span>
            <div className="text-center">
                <p className="font-semibold text-sm">{option.label}</p>
                <p className="text-xs text-muted-foreground mt-1">{option.desc}</p>
            </div>
        </motion.button>
    );
}

// ── Toggle Card (for content preferences) ────────────────────

function ToggleCard({
    label,
    desc,
    emoji,
    enabled,
    onToggle,
}: {
    label: string;
    desc: string;
    emoji: string;
    enabled: boolean;
    onToggle: () => void;
}) {
    return (
        <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={onToggle}
            className={cn(
                "flex items-center gap-4 p-5 rounded-xl border-2 transition-all duration-200 w-full text-left",
                enabled
                    ? "border-primary bg-primary/10"
                    : "border-border bg-card hover:border-primary/40"
            )}
        >
            <span className="text-3xl">{emoji}</span>
            <div className="flex-1">
                <p className="font-semibold text-sm">{label}</p>
                <p className="text-xs text-muted-foreground">{desc}</p>
            </div>
            <div
                className={cn(
                    "w-12 h-7 rounded-full transition-colors relative",
                    enabled ? "bg-primary" : "bg-muted"
                )}
            >
                <motion.div
                    animate={{ x: enabled ? 22 : 2 }}
                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                    className="absolute top-1 w-5 h-5 bg-white rounded-full shadow"
                />
            </div>
        </motion.button>
    );
}

// ── Main page ────────────────────────────────────────────────

export default function TrashGuidesPage() {
    const { data: status, isLoading: statusLoading, isError: statusError } = useTrashStatus();
    const syncMutation = useTrashSync();
    const recommendMutation = useTrashRecommend();
    const applyMutation = useTrashApply();
    const { data: services } = useServices();
    const { toast } = useToast();

    const [step, setStep] = useState(0);
    const [prefs, setPrefs] = useState<MediaPreferences>({
        display_type: "dv_hdr10_fallback",
        audio_type: "atmos",
        language: "vo",
        quality: "1080p",
        watches_anime: false,
        watches_french_series: false,
    });
    const [recommendations, setRecommendations] = useState<RecommendedProfile[] | null>(null);
    const [showApplyDialog, setShowApplyDialog] = useState(false);
    const [applyResults, setApplyResults] = useState<Record<number, ApplyResult>>({});

    const handleSync = async () => {
        try {
            await syncMutation.mutateAsync(true);
            toast({ title: "Synchronisation réussie", description: "Données TRaSH Guides mises à jour" });
        } catch {
            toast({ title: "Erreur", description: "Impossible de synchroniser", variant: "destructive" });
        }
    };

    const handleNext = async () => {
        if (step < STEPS.length - 1) {
            setStep(step + 1);

            // Fetch recommendations when going to review step
            if (step === STEPS.length - 2) {
                try {
                    const recs = await recommendMutation.mutateAsync(prefs);
                    setRecommendations(recs);
                } catch {
                    toast({
                        title: "Erreur",
                        description: "Impossible de générer les recommandations. Vérifiez que les données TRaSH sont synchronisées.",
                        variant: "destructive",
                    });
                }
            }
        }
    };

    const handleBack = () => {
        if (step > 0) setStep(step - 1);
    };

    const currentStep = STEPS[step];

    if (statusLoading && !statusError) {
        return (
            <>
                <Header title="TRaSH Guides" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    return (
        <>
            <Header title="TRaSH Guides" />
            <div className="p-6 space-y-6 max-w-4xl mx-auto">
                {/* Header section */}
                <div className="flex items-start justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight flex items-center gap-2">
                            <Sparkles className="h-6 w-6 text-primary" />
                            Profil Média
                        </h2>
                        <p className="text-sm text-muted-foreground mt-1">
                            Configurez vos préférences pour optimiser automatiquement Sonarr & Radarr
                            selon les meilleures pratiques TRaSH Guides.
                        </p>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleSync}
                        disabled={syncMutation.isPending}
                        className="gap-2"
                    >
                        {syncMutation.isPending ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <RefreshCw className="h-4 w-4" />
                        )}
                        Sync
                    </Button>
                </div>

                {/* Cache status */}
                {status && (
                    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                        <Card className="bg-card/50">
                            <CardContent className="p-4">
                                <div className="flex items-center gap-6 text-sm">
                                    <div className="flex items-center gap-2">
                                        <div className={cn(
                                            "h-2 w-2 rounded-full",
                                            status.is_stale ? "bg-amber-500" : "bg-green-500"
                                        )} />
                                        <span className="text-muted-foreground">
                                            {status.is_stale ? "Cache périmé" : "Cache à jour"}
                                        </span>
                                    </div>
                                    <Badge variant="outline" className="font-mono text-xs">
                                        {status.sonarr_cf_count} CFs Sonarr
                                    </Badge>
                                    <Badge variant="outline" className="font-mono text-xs">
                                        {status.radarr_cf_count} CFs Radarr
                                    </Badge>
                                    {status.cache_age_hours !== null && (
                                        <span className="text-xs text-muted-foreground">
                                            Mis à jour il y a {status.cache_age_hours.toFixed(1)}h
                                        </span>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </motion.div>
                )}

                {/* Step progress */}
                <div className="flex items-center gap-1">
                    {STEPS.map((s, i) => {
                        const Icon = s.icon;
                        const isActive = i === step;
                        const isDone = i < step;
                        return (
                            <div key={s.id} className="flex items-center gap-1 flex-1">
                                <button
                                    onClick={() => i <= step && setStep(i)}
                                    className={cn(
                                        "flex items-center gap-2 px-3 py-2 rounded-lg transition-all text-xs font-medium flex-1 justify-center",
                                        isActive && "bg-primary text-primary-foreground shadow-md",
                                        isDone && "bg-primary/20 text-primary cursor-pointer",
                                        !isActive && !isDone && "bg-muted text-muted-foreground"
                                    )}
                                >
                                    {isDone ? (
                                        <CheckCircle className="h-3.5 w-3.5" />
                                    ) : (
                                        <Icon className="h-3.5 w-3.5" />
                                    )}
                                    <span className="hidden sm:inline">{s.title}</span>
                                </button>
                                {i < STEPS.length - 1 && (
                                    <div className={cn(
                                        "h-0.5 w-4 rounded",
                                        i < step ? "bg-primary" : "bg-muted"
                                    )} />
                                )}
                            </div>
                        );
                    })}
                </div>

                {/* Step content */}
                <AnimatePresence mode="wait">
                    <motion.div
                        key={step}
                        initial={{ opacity: 0, x: 20 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -20 }}
                        transition={{ duration: 0.2 }}
                    >
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-lg flex items-center gap-2">
                                    {(() => {
                                        const Icon = currentStep.icon;
                                        return <Icon className="h-5 w-5 text-primary" />;
                                    })()}
                                    {step === 0 && "Quel type d'écran utilisez-vous ?"}
                                    {step === 1 && "Quel système audio avez-vous ?"}
                                    {step === 2 && "En quelle langue regardez-vous ?"}
                                    {step === 3 && "Quelle qualité préférez-vous ?"}
                                    {step === 4 && "Quel contenu regardez-vous ?"}
                                    {step === 5 && "Vos recommandations TRaSH Guides"}
                                </CardTitle>
                                <CardDescription>
                                    {step === 0 && "Cela détermine les formats HDR à privilégier"}
                                    {step === 1 && "Cela détermine les codecs audio à scorer"}
                                    {step === 2 && "Les Custom Formats de langue seront ajustés en conséquence"}
                                    {step === 3 && "Le Quality Profile sera adapté à votre choix"}
                                    {step === 4 && "Active les Custom Formats spéciaux pour vos types de contenu"}
                                    {step === 5 && "Voici la configuration optimale basée sur vos préférences"}
                                </CardDescription>
                            </CardHeader>
                            <CardContent>
                                {/* Display step */}
                                {step === 0 && (
                                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                                        {DISPLAY_OPTIONS.map((opt) => (
                                            <OptionCard
                                                key={opt.value}
                                                option={opt}
                                                selected={prefs.display_type === opt.value}
                                                onClick={() =>
                                                    setPrefs({ ...prefs, display_type: opt.value as MediaPreferences["display_type"] })
                                                }
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Audio step */}
                                {step === 1 && (
                                    <div className="grid grid-cols-2 gap-3">
                                        {AUDIO_OPTIONS.map((opt) => (
                                            <OptionCard
                                                key={opt.value}
                                                option={opt}
                                                selected={prefs.audio_type === opt.value}
                                                onClick={() =>
                                                    setPrefs({ ...prefs, audio_type: opt.value as MediaPreferences["audio_type"] })
                                                }
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Language step */}
                                {step === 2 && (
                                    <div className="grid grid-cols-2 gap-3">
                                        {LANGUAGE_OPTIONS.map((opt) => (
                                            <OptionCard
                                                key={opt.value}
                                                option={opt}
                                                selected={prefs.language === opt.value}
                                                onClick={() =>
                                                    setPrefs({ ...prefs, language: opt.value as MediaPreferences["language"] })
                                                }
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Quality step */}
                                {step === 3 && (
                                    <div className="grid grid-cols-2 gap-3">
                                        {QUALITY_OPTIONS.map((opt) => (
                                            <OptionCard
                                                key={opt.value}
                                                option={opt}
                                                selected={prefs.quality === opt.value}
                                                onClick={() =>
                                                    setPrefs({ ...prefs, quality: opt.value as MediaPreferences["quality"] })
                                                }
                                            />
                                        ))}
                                    </div>
                                )}

                                {/* Content step */}
                                {step === 4 && (
                                    <div className="space-y-3">
                                        <ToggleCard
                                            emoji="🎌"
                                            label="Anime"
                                            desc="Active les Custom Formats anime : fansub tiers, dual audio, groupes BD/Web"
                                            enabled={prefs.watches_anime}
                                            onToggle={() => setPrefs({ ...prefs, watches_anime: !prefs.watches_anime })}
                                        />
                                        <ToggleCard
                                            emoji="🇫🇷"
                                            label="Séries françaises"
                                            desc="Active les Custom Formats français : groupes FR, scène française, MyCanal, ADN"
                                            enabled={prefs.watches_french_series}
                                            onToggle={() =>
                                                setPrefs({ ...prefs, watches_french_series: !prefs.watches_french_series })
                                            }
                                        />
                                    </div>
                                )}

                                {/* Review step */}
                                {step === 5 && (
                                    <div className="space-y-4">
                                        {recommendMutation.isPending && (
                                            <div className="flex items-center justify-center py-12">
                                                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                                                <span className="ml-3 text-muted-foreground">
                                                    Calcul des recommandations…
                                                </span>
                                            </div>
                                        )}

                                        {recommendations && recommendations.length > 0 && (
                                            <>
                                                {/* Summary badges */}
                                                <div className="flex flex-wrap gap-2 p-4 bg-muted/30 rounded-lg">
                                                    <Badge variant="outline">
                                                        {DISPLAY_OPTIONS.find((o) => o.value === prefs.display_type)?.emoji}{" "}
                                                        {DISPLAY_OPTIONS.find((o) => o.value === prefs.display_type)?.label}
                                                    </Badge>
                                                    <Badge variant="outline">
                                                        {AUDIO_OPTIONS.find((o) => o.value === prefs.audio_type)?.emoji}{" "}
                                                        {AUDIO_OPTIONS.find((o) => o.value === prefs.audio_type)?.label}
                                                    </Badge>
                                                    <Badge variant="outline">
                                                        {LANGUAGE_OPTIONS.find((o) => o.value === prefs.language)?.emoji}{" "}
                                                        {LANGUAGE_OPTIONS.find((o) => o.value === prefs.language)?.label}
                                                    </Badge>
                                                    <Badge variant="outline">
                                                        {QUALITY_OPTIONS.find((o) => o.value === prefs.quality)?.emoji}{" "}
                                                        {QUALITY_OPTIONS.find((o) => o.value === prefs.quality)?.label}
                                                    </Badge>
                                                    {prefs.watches_anime && (
                                                        <Badge variant="outline">🎌 Anime</Badge>
                                                    )}
                                                    {prefs.watches_french_series && (
                                                        <Badge variant="outline">🇫🇷 Séries FR</Badge>
                                                    )}
                                                </div>

                                                {/* Recommendations per profile */}
                                                {recommendations.map((rec) => (
                                                    <Card key={`${rec.service_type}-${rec.profile_id}`} className="bg-card/50">
                                                        <CardHeader className="pb-3">
                                                            <div className="flex items-center justify-between">
                                                                <CardTitle className="text-sm flex items-center gap-2">
                                                                    <Shield className="h-4 w-4 text-primary" />
                                                                    {rec.service_type === "sonarr" ? "📺 Sonarr" : "🎬 Radarr"}
                                                                    <span className="text-muted-foreground">—</span>
                                                                    <span className="font-mono text-xs">{rec.profile_name}</span>
                                                                </CardTitle>
                                                                <Badge className="text-xs">
                                                                    {rec.custom_formats.length} Custom Formats
                                                                </Badge>
                                                            </div>
                                                            <CardDescription className="text-xs">
                                                                {rec.description}
                                                            </CardDescription>
                                                        </CardHeader>
                                                        <CardContent>
                                                            <div className="flex flex-wrap gap-1.5">
                                                                {rec.custom_formats.slice(0, 30).map((cf) => (
                                                                    <Badge
                                                                        key={cf.trash_id}
                                                                        variant="outline"
                                                                        className={cn(
                                                                            "text-[10px] font-mono",
                                                                            cf.category === "hdr" && "border-amber-500/40 text-amber-400",
                                                                            cf.category === "audio" && "border-blue-500/40 text-blue-400",
                                                                            cf.category === "language" && "border-green-500/40 text-green-400",
                                                                            cf.category === "anime" && "border-pink-500/40 text-pink-400",
                                                                            cf.category === "unwanted" && "border-red-500/40 text-red-400",
                                                                            cf.category === "quality" && "border-purple-500/40 text-purple-400",
                                                                        )}
                                                                    >
                                                                        {cf.name}
                                                                    </Badge>
                                                                ))}
                                                                {rec.custom_formats.length > 30 && (
                                                                    <Badge variant="outline" className="text-[10px]">
                                                                        +{rec.custom_formats.length - 30} autres
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        </CardContent>
                                                    </Card>
                                                ))}
                                            </>
                                        )}

                                        {recommendations && recommendations.length === 0 && (
                                            <div className="text-center py-8 text-muted-foreground">
                                                Aucune recommandation générée. Vérifiez la synchronisation.
                                            </div>
                                        )}
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </motion.div>
                </AnimatePresence>

                {/* Navigation buttons */}
                <div className="flex justify-between">
                    <Button
                        variant="outline"
                        onClick={handleBack}
                        disabled={step === 0}
                        className="gap-2"
                    >
                        <ArrowLeft className="h-4 w-4" />
                        Précédent
                    </Button>

                    {step < STEPS.length - 1 ? (
                        <Button onClick={handleNext} className="gap-2">
                            Suivant
                            <ArrowRight className="h-4 w-4" />
                        </Button>
                    ) : (
                        <Button
                            className="gap-2"
                            disabled={!recommendations || recommendations.length === 0}
                            onClick={() => setShowApplyDialog(true)}
                        >
                            <Zap className="h-4 w-4" />
                            Appliquer
                        </Button>
                    )}
                </div>

                {/* Apply Dialog */}
                <AnimatePresence>
                    {showApplyDialog && (
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
                            onClick={() => !applyMutation.isPending && setShowApplyDialog(false)}
                        >
                            <motion.div
                                initial={{ scale: 0.9, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                exit={{ scale: 0.9, opacity: 0 }}
                                onClick={(e) => e.stopPropagation()}
                                className="w-full max-w-lg mx-4"
                            >
                                <Card>
                                    <CardHeader>
                                        <CardTitle className="flex items-center gap-2">
                                            <Zap className="h-5 w-5 text-primary" />
                                            Appliquer les Custom Formats
                                        </CardTitle>
                                        <CardDescription>
                                            Les CFs recommandés seront créés ou mis à jour dans vos services.
                                        </CardDescription>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        {/* Service list */}
                                        {services && services.filter(s =>
                                            s.type.toLowerCase() === "sonarr" || s.type.toLowerCase() === "radarr"
                                        ).length > 0 ? (
                                            <div className="space-y-2">
                                                {services
                                                    .filter(s => s.type.toLowerCase() === "sonarr" || s.type.toLowerCase() === "radarr")
                                                    .map((svc) => {
                                                        const serviceRecs = recommendations?.filter(
                                                            r => r.service_type === svc.type.toLowerCase()
                                                        ) || [];
                                                        const alreadyApplied = applyResults[svc.id];

                                                        return (
                                                            <div
                                                                key={svc.id}
                                                                className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/30"
                                                            >
                                                                <div className="flex items-center gap-3">
                                                                    <span className={cn(
                                                                        "h-2.5 w-2.5 rounded-full",
                                                                        svc.last_status === "online" ? "bg-green-500" : "bg-red-500"
                                                                    )} />
                                                                    <div>
                                                                        <p className="text-sm font-medium">{svc.name}</p>
                                                                        <p className="text-xs text-muted-foreground">
                                                                            {svc.type} — {serviceRecs.length} profil(s) à appliquer
                                                                        </p>
                                                                    </div>
                                                                </div>

                                                                {alreadyApplied ? (
                                                                    <Badge
                                                                        variant={alreadyApplied.success ? "default" : "destructive"}
                                                                        className="gap-1"
                                                                    >
                                                                        <CheckCircle className="h-3 w-3" />
                                                                        {alreadyApplied.cfs_created} créés, {alreadyApplied.cfs_updated} MàJ
                                                                    </Badge>
                                                                ) : (
                                                                    <Button
                                                                        size="sm"
                                                                        disabled={applyMutation.isPending || serviceRecs.length === 0 || svc.last_status !== "online"}
                                                                        onClick={async () => {
                                                                            try {
                                                                                const profileIds = serviceRecs.map(r => r.profile_id);
                                                                                const result = await applyMutation.mutateAsync({
                                                                                    service_id: svc.id,
                                                                                    recommendations: profileIds,
                                                                                });
                                                                                setApplyResults(prev => ({ ...prev, [svc.id]: result }));
                                                                                toast({
                                                                                    title: `${svc.name} — Appliqué !`,
                                                                                    description: `${result.cfs_created} CFs créés, ${result.cfs_updated} mis à jour`,
                                                                                });
                                                                            } catch {
                                                                                toast({
                                                                                    title: "Erreur",
                                                                                    description: `Impossible d'appliquer à ${svc.name}`,
                                                                                    variant: "destructive",
                                                                                });
                                                                            }
                                                                        }}
                                                                        className="gap-1"
                                                                    >
                                                                        {applyMutation.isPending ? (
                                                                            <Loader2 className="h-3 w-3 animate-spin" />
                                                                        ) : (
                                                                            <Zap className="h-3 w-3" />
                                                                        )}
                                                                        Appliquer
                                                                    </Button>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                            </div>
                                        ) : (
                                            <div className="text-center py-6 text-muted-foreground">
                                                Aucun service Sonarr/Radarr configuré.
                                                <br />
                                                <span className="text-xs">Ajoutez-en via la page Services.</span>
                                            </div>
                                        )}

                                        {/* Close button */}
                                        <div className="flex justify-end pt-2">
                                            <Button
                                                variant="outline"
                                                onClick={() => {
                                                    setShowApplyDialog(false);
                                                    setApplyResults({});
                                                }}
                                                disabled={applyMutation.isPending}
                                            >
                                                Fermer
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </>
    );
}
