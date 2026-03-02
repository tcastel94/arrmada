"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
} from "lucide-react";
import { useSettings, useTestTelegram } from "@/hooks/use-settings";
import { useServices } from "@/hooks/use-services";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

function ConfigItem({
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
        <div className="flex items-center justify-between py-3">
            <div className="flex items-center gap-3">
                <Icon className="h-4 w-4 text-muted-foreground" />
                <div>
                    <p className="text-sm font-medium">{label}</p>
                    <p className="text-xs text-muted-foreground">{value}</p>
                </div>
            </div>
            <Badge variant={configured ? "default" : "destructive"} className="gap-1">
                {configured ? (
                    <CheckCircle className="h-3 w-3" />
                ) : (
                    <XCircle className="h-3 w-3" />
                )}
                {configured ? "Configuré" : "Non configuré"}
            </Badge>
        </div>
    );
}

export default function SettingsPage() {
    const { data: settings, isLoading } = useSettings();
    const { data: services } = useServices();
    const testTelegram = useTestTelegram();
    const { toast } = useToast();

    const handleTestTelegram = async () => {
        try {
            const result = (await testTelegram.mutateAsync(undefined)) as { success: boolean };
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
            <div className="p-6 space-y-6 max-w-3xl">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Paramètres</h2>
                    <p className="text-sm text-muted-foreground">
                        Configuration de l&apos;application ArrMada
                    </p>
                </div>

                {/* Notifications */}
                <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Bell className="h-4 w-4" />
                                Notifications Telegram
                            </CardTitle>
                            <CardDescription>
                                Recevez des alertes quand un service tombe ou redémarre, et quand
                                un téléchargement termine
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <ConfigItem
                                label="Bot Token"
                                value={
                                    settings.telegram.bot_token_set
                                        ? "Configuré dans .env"
                                        : "TELEGRAM_BOT_TOKEN non défini"
                                }
                                configured={settings.telegram.bot_token_set}
                                icon={Key}
                            />
                            <Separator />
                            <ConfigItem
                                label="Chat ID"
                                value={
                                    settings.telegram.chat_id_set
                                        ? "Configuré dans .env"
                                        : "TELEGRAM_CHAT_ID non défini"
                                }
                                configured={settings.telegram.chat_id_set}
                                icon={Send}
                            />
                            <Separator />
                            <div className="pt-2">
                                <Button
                                    variant="outline"
                                    onClick={handleTestTelegram}
                                    disabled={!settings.telegram.configured || testTelegram.isPending}
                                >
                                    {testTelegram.isPending ? (
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                    ) : (
                                        <Send className="h-4 w-4 mr-2" />
                                    )}
                                    Envoyer un test
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Connected Services */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Server className="h-4 w-4" />
                                Services connectés
                            </CardTitle>
                            <CardDescription>
                                Résumé des services *arr configurés
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {services && services.length > 0 ? (
                                <div className="space-y-2">
                                    {services.map((svc) => (
                                        <div
                                            key={svc.id}
                                            className="flex items-center justify-between py-2 px-3 rounded-md hover:bg-muted/50 transition-colors"
                                        >
                                            <div className="flex items-center gap-3">
                                                <span
                                                    className={cn(
                                                        "h-2 w-2 rounded-full",
                                                        svc.last_status === "online"
                                                            ? "bg-green-500"
                                                            : "bg-red-500"
                                                    )}
                                                />
                                                <span className="text-sm font-medium">{svc.name}</span>
                                                <Badge variant="outline" className="text-[10px]">
                                                    {svc.type}
                                                </Badge>
                                            </div>
                                            <span className="text-xs text-muted-foreground font-mono">
                                                {svc.url}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="text-sm text-muted-foreground">
                                    Aucun service configuré
                                </p>
                            )}
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Application Config */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                >
                    <Card>
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Shield className="h-4 w-4" />
                                Application
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            <ConfigItem
                                label="Authentification"
                                value={`Session JWT de ${settings.auth.jwt_expiration_hours}h`}
                                configured={true}
                                icon={Shield}
                            />
                            <Separator />
                            <ConfigItem
                                label="TMDB"
                                value={
                                    settings.tmdb.configured
                                        ? "Clé API configurée"
                                        : "TMDB_API_KEY non définie (optionnel)"
                                }
                                configured={settings.tmdb.configured}
                                icon={Film}
                            />
                            <Separator />
                            <ConfigItem
                                label="CORS Origins"
                                value={settings.cors.origins.join(", ")}
                                configured={true}
                                icon={Globe}
                            />
                            <Separator />
                            <ConfigItem
                                label="Health Checks"
                                value={`Intervalle: ${settings.scheduler.health_check_interval}`}
                                configured={true}
                                icon={Clock}
                            />
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Profile Overrides */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.25 }}
                >
                    <a href="/settings/profile-overrides">
                        <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
                            <CardContent className="flex items-center gap-4 p-4">
                                <div className="rounded-full p-2.5 bg-primary/10">
                                    <Target className="h-5 w-5 text-primary" />
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-semibold">Profils TRaSH par média</p>
                                    <p className="text-xs text-muted-foreground">
                                        Assigner un profil TRaSH spécifique à une série ou un film
                                    </p>
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </CardContent>
                        </Card>
                    </a>
                </motion.div>

                {/* SABnzbd TRaSH Config */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    <a href="/settings/sabnzbd-config">
                        <Card className="hover:bg-muted/50 transition-colors cursor-pointer">
                            <CardContent className="flex items-center gap-4 p-4">
                                <div className="rounded-full p-2.5 bg-orange-500/10">
                                    <Shield className="h-5 w-5 text-orange-400" />
                                </div>
                                <div className="flex-1">
                                    <p className="text-sm font-semibold">SABnzbd — TRaSH Config</p>
                                    <p className="text-xs text-muted-foreground">
                                        Audit et optimisation SABnzbd selon les recommandations TRaSH Guides
                                    </p>
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </CardContent>
                        </Card>
                    </a>
                </motion.div>

                {/* App Info */}
                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                >
                    <Card>
                        <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-sm font-semibold">ArrMada</p>
                                    <p className="text-xs text-muted-foreground">
                                        v0.1.0 — Unified *arr stack management
                                    </p>
                                </div>
                                <Badge variant="outline" className="font-mono text-xs">
                                    FastAPI + Next.js 14
                                </Badge>
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </div>
        </>
    );
}
