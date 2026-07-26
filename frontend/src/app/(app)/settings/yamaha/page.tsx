"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyState } from "@/components/shared/empty-state";
import {
    Speaker,
    Trash2,
    CheckCircle2,
    XCircle,
    Loader2,
    Plus,
    Radar,
} from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
    useYamahaSettings,
    useAddYamaha,
    useDeleteYamaha,
    useTestYamaha,
    useYamahaDiscover,
    type YamahaInstance,
} from "@/hooks/use-yamaha";
import { YamahaRemote } from "@/components/yamaha-remote";

function InstanceRow({ y }: { y: YamahaInstance }) {
    const test = useTestYamaha();
    const del = useDeleteYamaha();
    const [result, setResult] = useState<null | { ok: boolean; label: string }>(null);

    const runTest = () =>
        test.mutate(y.id, {
            onSuccess: (r) =>
                setResult(
                    r.ok
                        ? { ok: true, label: `${r.model} · ${r.power} · ${r.volume_pct}%` }
                        : { ok: false, label: r.detail || "injoignable" },
                ),
            onError: (e) => setResult({ ok: false, label: e.message }),
        });

    return (
        <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/40 p-3">
            <Speaker className="h-5 w-5 text-orange-400 shrink-0" />
            <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{y.name}</p>
                <p className="text-xs text-muted-foreground font-mono truncate">{y.url}</p>
            </div>
            {result && (
                <span className={`text-xs flex items-center gap-1 ${result.ok ? "text-emerald-400" : "text-red-400"}`}>
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
                onClick={() => del.mutate(y.id, { onSuccess: () => toast.success("Ampli supprimé.") })}
            >
                <Trash2 className="h-4 w-4" />
            </Button>
        </div>
    );
}

export default function YamahaSettingsPage() {
    const { data: instances, isLoading } = useYamahaSettings();
    const add = useAddYamaha();
    const discover = useYamahaDiscover();

    const [name, setName] = useState("Ampli Yamaha");
    const [url, setUrl] = useState("http://192.168.2.70");

    const submit = () => {
        if (!url) return;
        add.mutate(
            { name, url, is_enabled: true },
            {
                onSuccess: (r) => toast.success(r.message || "Ampli enregistré."),
                onError: (e) => toast.error("Échec : " + e.message),
            },
        );
    };

    const hasInstances = instances && instances.length > 0;

    return (
        <>
            <Header title="Ampli Yamaha" />
            <motion.div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                {/* Live control */}
                {hasInstances && (
                    <Card className="bg-card/40 border-border/50">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-base">
                                <Speaker className="h-5 w-5 text-orange-400" /> Télécommande
                            </CardTitle>
                            <CardDescription>Marche/veille, volume, sourdine et sélection d&apos;entrée en direct.</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <YamahaRemote card={false} />
                        </CardContent>
                    </Card>
                )}

                {/* Instances */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Speaker className="h-5 w-5 text-orange-400" /> Amplis configurés
                        </CardTitle>
                        <CardDescription>Les récepteurs Yamaha (MusicCast / YamahaExtendedControl) de ton réseau.</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {isLoading ? (
                            <div className="h-16 rounded-lg bg-muted/15 animate-pulse" />
                        ) : hasInstances ? (
                            instances!.map((y) => <InstanceRow key={y.id} y={y} />)
                        ) : (
                            <EmptyState icon={Speaker} title="Aucun ampli" description="Détecte ou ajoute ton ampli ci-dessous." />
                        )}
                    </CardContent>
                </Card>

                {/* Add */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="text-base">Ajouter un ampli</CardTitle>
                        <CardDescription>L&apos;ampli doit être connecté au réseau (aucune authentification requise).</CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <Label className="text-xs">Nom</Label>
                                <Input value={name} onChange={(e) => setName(e.target.value)} className="border-white/10 bg-transparent" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">URL / IP</Label>
                                <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://192.168.2.70" className="border-white/10 bg-transparent font-mono text-sm" />
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
                                                setName(list[0].model_name || "Yamaha");
                                                setUrl(list[0].url);
                                                toast.success(
                                                    list.length === 1
                                                        ? `${list[0].model_name} détecté — champs pré-remplis.`
                                                        : `${list.length} amplis détectés : ${list.map((l) => l.model_name).join(", ")}`,
                                                );
                                            } else {
                                                toast.info("Aucun ampli Yamaha détecté sur le réseau.");
                                            }
                                        },
                                        onError: (e) => toast.error("Découverte échouée : " + e.message),
                                    })
                                }
                            >
                                {discover.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Radar className="h-4 w-4 mr-2" />}
                                Détecter sur le réseau
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </>
    );
}
