"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Settings,
    Bell,
    Shield,
    Globe,
    Clock,
    Film,
    CheckCircle,
    XCircle,
    Send,
    Loader2,
    Server,
    Key,
    Target,
    ChevronRight,
    Cog,
    Palette,
} from "lucide-react";
import { useSettings, useTestTelegram } from "@/hooks/use-settings";
import { useServices } from "@/hooks/use-services";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import Link from "next/link";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.06 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 14 },
    show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
};

function ConfigRow({
    label,
    value,
    configured,
    icon: Icon,
}: {
    label: string;
    value: string;
    configured: boolean;
    icon: any;
}) {
    return (
        <div className="flex items-center justify-between py-3 px-1 group">
            <div className="flex items-center gap-3">
                <div
                    className={cn(
                        "rounded-lg p-1.5",
                        configured
                            ? "bg-emerald-500/10 text-emerald-400"
                            : "bg-red-500/10 text-red-400"
                    )}
                >
                    <Icon className="h-3.5 w-3.5" />
                </div>
                <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{value}</p>
                </div>
            </div>
            <Badge
                variant="outline"
                className={cn(
                    "gap-1 text-[10px] h-5",
                    configured
                        ? "border-emerald-500/30 text-emerald-400"
                        : "border-red-500/30 text-red-400"
                )}
            >
                {configured ? (
                    <CheckCircle className="h-3 w-3" />
                ) : (
                    <XCircle className="h-3 w-3" />
                )}
                {configured ? "OK" : "Non configuré"}
            </Badge>
        </div>
    );
}

function SettingsLink({
    href,
    icon: Icon,
    iconColor,
    iconBg,
    title,
    description,
}: {
    href: string;
    icon: any;
    iconColor: string;
    iconBg: string;
    title: string;
    description: string;
}) {
    return (
        <motion.div variants={fadeUp}>
            <Link href={href}>
                <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm hover:ring-white/15 hover:scale-[1.01] transition-all duration-200 cursor-pointer group">
                    <CardContent className="flex items-center gap-4 p-4">
                        <div className={cn("rounded-xl p-2.5", iconBg)}>
                            <Icon className={cn("h-5 w-5", iconColor)} />
                        </div>
                        <div className="flex-1">
                            <p className="text-sm font-semibold">{title}</p>
                            <p className="text-xs text-muted-foreground mt-0.5">
                                {description}
                            </p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-foreground transition-colors" />
                    </CardContent>
                </Card>
            </Link>
        </motion.div>
    );
}

export default function SettingsPage() {
    const { data: settings, isLoading } = useSettings();
    const { data: services } = useServices();
    const testTelegram = useTestTelegram();
    const { toast } = useToast();

    const handleTestTelegram = async () => {
        try {
            const result = (await testTelegram.mutateAsync(undefined)) as {
                success: boolean;
            };
            if (result.success) {
                toast({
                    title: "Notification envoyée",
                    description: "Vérifiez votre chat Telegram",
                });
            } else {
                toast({
                    title: "Échec",
                    description: "Telegram n'a pas répondu",
                    variant: "destructive",
                });
            }
        } catch {
            toast({
                title: "Erreur",
                description: "Impossible d'envoyer la notification",
                variant: "destructive",
            });
        }
    };

    if (isLoading) {
        return (
            <>
                <Header title="Paramètres" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    if (!settings) return null;

    return (
        <>
            <Header title="Paramètres" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-3xl mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-slate-600/20 via-zinc-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center gap-4">
                            <div className="rounded-xl bg-slate-500/20 p-3">
                                <Cog className="h-6 w-6 text-slate-400" />
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold tracking-tight">
                                    Paramètres
                                </h2>
                                <p className="text-sm text-muted-foreground mt-0.5">
                                    Configuration de l&apos;application ArrMada
                                </p>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-slate-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Telegram */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <CardContent className="p-0">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                    <Bell className="h-4 w-4 text-blue-400" />
                                    <span className="text-sm font-semibold">
                                        Notifications Telegram
                                    </span>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={cn(
                                        "text-[10px]",
                                        settings.telegram.configured
                                            ? "border-emerald-500/30 text-emerald-400"
                                            : "border-red-500/30 text-red-400"
                                    )}
                                >
                                    {settings.telegram.configured ? "Actif" : "Inactif"}
                                </Badge>
                            </div>
                            <div className="px-5 py-3 space-y-1 divide-y divide-white/5">
                                <ConfigRow
                                    label="Bot Token"
                                    value={
                                        settings.telegram.bot_token_set
                                            ? "Configuré dans .env"
                                            : "TELEGRAM_BOT_TOKEN non défini"
                                    }
                                    configured={settings.telegram.bot_token_set}
                                    icon={Key}
                                />
                                <ConfigRow
                                    label="Chat ID"
                                    value={
                                        settings.telegram.chat_id_set
                                            ? "Configuré dans .env"
                                            : "TELEGRAM_CHAT_ID non défini"
                                    }
                                    configured={settings.telegram.chat_id_set}
                                    icon={Send}
                                />
                            </div>
                            <div className="px-5 pb-4 pt-1">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={handleTestTelegram}
                                    disabled={
                                        !settings.telegram.configured ||
                                        testTelegram.isPending
                                    }
                                    className="gap-2 border-white/10"
                                >
                                    {testTelegram.isPending ? (
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                    ) : (
                                        <Send className="h-3.5 w-3.5" />
                                    )}
                                    Envoyer un test
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Services Summary */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <CardContent className="p-0">
                            <div className="flex items-center justify-between px-5 py-3 border-b border-white/5">
                                <div className="flex items-center gap-2">
                                    <Server className="h-4 w-4 text-indigo-400" />
                                    <span className="text-sm font-semibold">
                                        Services connectés
                                    </span>
                                </div>
                                <Badge variant="outline" className="text-[10px]">
                                    {services?.length ?? 0} service{(services?.length ?? 0) > 1 ? "s" : ""}
                                </Badge>
                            </div>
                            <div className="px-5 py-3">
                                {services && services.length > 0 ? (
                                    <div className="space-y-1 divide-y divide-white/5">
                                        {services.map((svc) => (
                                            <div
                                                key={svc.id}
                                                className="flex items-center justify-between py-2.5"
                                            >
                                                <div className="flex items-center gap-3">
                                                    <div className="relative">
                                                        <span
                                                            className={cn(
                                                                "block h-2.5 w-2.5 rounded-full",
                                                                svc.last_status === "online"
                                                                    ? "bg-emerald-400"
                                                                    : "bg-red-400"
                                                            )}
                                                        />
                                                        {svc.last_status === "online" && (
                                                            <span className="absolute inset-0 rounded-full bg-emerald-400 animate-ping opacity-30" />
                                                        )}
                                                    </div>
                                                    <span className="text-sm font-medium">
                                                        {svc.name}
                                                    </span>
                                                    <Badge
                                                        variant="outline"
                                                        className="text-[10px] h-4 px-1.5 border-white/10"
                                                    >
                                                        {svc.type}
                                                    </Badge>
                                                </div>
                                                <span className="text-xs text-muted-foreground/60 font-mono">
                                                    {svc.url}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <p className="text-sm text-muted-foreground py-4 text-center">
                                        Aucun service configuré
                                    </p>
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Application Config */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <CardContent className="p-0">
                            <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                <Shield className="h-4 w-4 text-emerald-400" />
                                <span className="text-sm font-semibold">
                                    Application
                                </span>
                            </div>
                            <div className="px-5 py-3 space-y-1 divide-y divide-white/5">
                                <ConfigRow
                                    label="Authentification"
                                    value={`Session JWT de ${settings.auth.jwt_expiration_hours}h`}
                                    configured={true}
                                    icon={Shield}
                                />
                                <ConfigRow
                                    label="TMDB"
                                    value={
                                        settings.tmdb.configured
                                            ? "Clé API configurée"
                                            : "TMDB_API_KEY non définie"
                                    }
                                    configured={settings.tmdb.configured}
                                    icon={Film}
                                />
                                <ConfigRow
                                    label="CORS Origins"
                                    value={settings.cors.origins.join(", ")}
                                    configured={true}
                                    icon={Globe}
                                />
                                <ConfigRow
                                    label="Health Checks"
                                    value={`Intervalle: ${settings.scheduler.health_check_interval}`}
                                    configured={true}
                                    icon={Clock}
                                />
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Quick Links */}
                <div className="space-y-2">
                    <SettingsLink
                        href="/settings/profile-overrides"
                        icon={Target}
                        iconColor="text-violet-400"
                        iconBg="bg-violet-500/20"
                        title="Profils TRaSH par média"
                        description="Assigner un profil TRaSH spécifique à une série ou un film"
                    />
                    <SettingsLink
                        href="/settings/sabnzbd-config"
                        icon={Shield}
                        iconColor="text-orange-400"
                        iconBg="bg-orange-500/20"
                        title="SABnzbd — TRaSH Config"
                        description="Audit et optimisation SABnzbd selon TRaSH Guides"
                    />
                </div>

                {/* App Info */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/20 backdrop-blur-sm">
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Palette className="h-4 w-4 text-muted-foreground/40" />
                                    <div>
                                        <p className="text-sm font-semibold">
                                            ArrMada
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            v0.1.0 — Unified *arr stack management
                                        </p>
                                    </div>
                                </div>
                                <Badge
                                    variant="outline"
                                    className="font-mono text-[10px] border-white/10"
                                >
                                    FastAPI + Next.js 14
                                </Badge>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </motion.div>
        </>
    );
}
