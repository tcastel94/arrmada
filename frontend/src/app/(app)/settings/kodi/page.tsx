"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import {
    MonitorPlay,
    Trash2,
    CheckCircle2,
    XCircle,
    Loader2,
    RefreshCw,
    Brush,
    Plus,
    Radar,
    AlertTriangle,
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
    useKodiSettings,
    useAddKodi,
    useDeleteKodi,
    useTestKodi,
    useKodiDiscover,
    useKodiSync,
    useKodiClean,
    useKodiDrift,
    type KodiInstance,
} from "@/hooks/use-kodi";

function InstanceRow({ k }: { k: KodiInstance }) {
    const test = useTestKodi();
    const del = useDeleteKodi();
    const [result, setResult] = useState<null | { ok: boolean; label: string }>(null);

    const runTest = () =>
        test.mutate(k.id, {
            onSuccess: (r) =>
                setResult(
                    r.ok
                        ? { ok: true, label: `${r.name} ${r.version}` }
                        : { ok: false, label: r.detail || "injoignable" },
                ),
            onError: (e) => setResult({ ok: false, label: e.message }),
        });

    return (
        <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/40 p-3">
            <MonitorPlay className="h-5 w-5 text-violet-400 shrink-0" />
            <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{k.name}</p>
                <p className="text-xs text-muted-foreground font-mono truncate">{k.url}</p>
            </div>
            {result && (
                <span
                    className={`text-xs flex items-center gap-1 ${result.ok ? "text-emerald-400" : "text-red-400"}`}
                >
                    {result.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                    {result.label}
                </span>
            )}
            <Button size="sm" variant="outline" className="border-white/10" disabled={test.isPending} onClick={runTest}>
                {test.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Tester"}
            </Button>
            <Button
                size="icon"
                variant="ghost"
                className="h-8 w-8 text-muted-foreground hover:text-red-400"
                onClick={() => del.mutate(k.id, { onSuccess: () => toast.success("Instance supprimée.") })}
            >
                <Trash2 className="h-4 w-4" />
            </Button>
        </div>
    );
}

export default function KodiSettingsPage() {
    const { data: instances, isLoading } = useKodiSettings();
    const add = useAddKodi();
    const discover = useKodiDiscover();
    const sync = useKodiSync();
    const clean = useKodiClean();
    const drift = useKodiDrift();

    const [name, setName] = useState("Kodi Salon");
    const [url, setUrl] = useState("http://192.168.2.140:8080");
    const [user, setUser] = useState("kodi");
    const [pass, setPass] = useState("");

    const submit = () => {
        if (!url) return;
        add.mutate(
            { name, url, api_key: `${user}:${pass}`, is_enabled: true },
            {
                onSuccess: (r) => {
                    toast.success(r.message || "Kodi enregistré.");
                    setPass("");
                },
                onError: (e) => toast.error("Échec : " + e.message),
            },
        );
    };

    return (
        <>
            <Header title="Kodi" />
            <motion.div
                className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
            >
                {/* Instances */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <MonitorPlay className="h-5 w-5 text-violet-400" /> Instances Kodi
                        </CardTitle>
                        <CardDescription>
                            Les lecteurs Kodi sur lesquels lire tes médias et déclencher les scans.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {isLoading ? (
                            <div className="h-16 rounded-lg bg-muted/15 animate-pulse" />
                        ) : instances && instances.length > 0 ? (
                            instances.map((k) => <InstanceRow key={k.id} k={k} />)
                        ) : (
                            <EmptyState icon={MonitorPlay} title="Aucun Kodi" description="Ajoute ton lecteur ci-dessous." />
                        )}
                    </CardContent>
                </Card>

                {/* Add */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="text-base">Ajouter un Kodi</CardTitle>
                        <CardDescription>
                            Active « Autoriser le contrôle à distance via HTTP » dans Kodi (Paramètres → Services → Contrôle).
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <Label className="text-xs">Nom</Label>
                                <Input value={name} onChange={(e) => setName(e.target.value)} className="border-white/10 bg-transparent" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">URL</Label>
                                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://IP:8080" className="border-white/10 bg-transparent font-mono text-sm" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Utilisateur</Label>
                                <Input value={user} onChange={(e) => setUser(e.target.value)} className="border-white/10 bg-transparent" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Mot de passe</Label>
                                <Input type="password" value={pass} onChange={(e) => setPass(e.target.value)} className="border-white/10 bg-transparent" />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2">
                            <Button onClick={submit} disabled={add.isPending}>
                                {add.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                                Enregistrer
                            </Button>
                            <Button
                                variant="outline"
                                className="border-white/10"
                                disabled={discover.isPending}
                                onClick={() =>
                                    discover.mutate(undefined, {
                                        onSuccess: (list) => {
                                            if (list && list.length > 0) {
                                                setName(list[0].name || "Kodi");
                                                setUrl(list[0].url);
                                                toast.success(`${list.length} Kodi détecté(s) — champs pré-remplis.`);
                                            } else {
                                                toast.info("Aucun Kodi détecté sur le réseau (mDNS).");
                                            }
                                        },
                                        onError: (e) => toast.error("Découverte échouée : " + e.message),
                                    })
                                }
                            >
                                {discover.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Radar className="h-4 w-4 mr-2" />}
                                Détecter (mDNS)
                            </Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Maintenance */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="text-base">Bibliothèque & maintenance</CardTitle>
                        <CardDescription>Synchronise, nettoie et vérifie la cohérence avec Radarr.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex flex-wrap gap-2">
                            <Button
                                variant="outline"
                                className="border-white/10"
                                disabled={sync.isPending}
                                onClick={() =>
                                    sync.mutate(undefined, {
                                        onSuccess: (r) => toast.success(`Scan lancé (${r.success} Kodi).`),
                                        onError: (e) => toast.error("Échec : " + e.message),
                                    })
                                }
                            >
                                {sync.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-2" />}
                                Scanner la bibliothèque
                            </Button>
                            <Button
                                variant="outline"
                                className="border-white/10"
                                disabled={clean.isPending}
                                onClick={() =>
                                    clean.mutate(undefined, {
                                        onSuccess: (r) =>
                                            r.status === "ok"
                                                ? toast.success("Nettoyage lancé sur Kodi.")
                                                : toast.error(r.detail || "Échec"),
                                        onError: (e) => toast.error("Échec : " + e.message),
                                    })
                                }
                            >
                                {clean.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Brush className="h-4 w-4 mr-2" />}
                                Nettoyer (entrées obsolètes)
                            </Button>
                        </div>

                        {/* Drift */}
                        <div className="rounded-lg border border-border/50 bg-background/30 p-3">
                            {drift.isLoading ? (
                                <div className="h-6 bg-muted/20 rounded animate-pulse" />
                            ) : drift.data ? (
                                drift.data.missing_count === 0 ? (
                                    <p className="text-sm text-emerald-400 flex items-center gap-2">
                                        <CheckCircle2 className="h-4 w-4" /> Radarr ({drift.data.radarr_total}) et Kodi ({drift.data.kodi_total}) sont synchronisés.
                                    </p>
                                ) : (
                                    <div className="space-y-2">
                                        <p className="text-sm text-amber-400 flex items-center gap-2">
                                            <AlertTriangle className="h-4 w-4" />
                                            {drift.data.missing_count} film(s) dans Radarr absent(s) de Kodi (à scanner).
                                        </p>
                                        <div className="flex flex-wrap gap-1.5">
                                            {drift.data.missing_in_kodi.slice(0, 20).map((m) => (
                                                <Badge key={m.tmdb_id} variant="outline" className="text-[10px] border-amber-500/30 text-amber-300">
                                                    {m.title}{m.year ? ` (${m.year})` : ""}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )
                            ) : (
                                <p className="text-sm text-muted-foreground">Cohérence Radarr ↔ Kodi indisponible.</p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </>
    );
}
