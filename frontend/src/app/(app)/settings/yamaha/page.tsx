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
    useYamahaProfiles,
    useSaveYamahaProfile,
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

                {/* Room Audio Profiles Configuration */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Speaker className="h-5 w-5 text-purple-400" /> Profils Acoustiques & Réglages Auto
                        </CardTitle>
                        <CardDescription>
                            Définis les paramètres sonores optimaux appliqués automatiquement lors du lancement d&apos;un média (Salon vs Salle de Cinéma).
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        <RoomProfilesEditor />
                    </CardContent>
                </Card>
            </motion.div>
        </>
    );
}

function RoomProfilesEditor() {
    const { data: profiles, isLoading } = useYamahaProfiles();
    const saveMutation = useSaveYamahaProfile();

    const salon = profiles?.salon ?? {
        name: "Salon",
        volume_pct: 40,
        volume_raw: 65,
        dialog_lift: 2,
        dialog_level: 2,
        movie_sound_program: "surround_decoder",
        series_sound_program: "drama",
        music_sound_program: "2ch_stereo",
        adaptive_drc: true,
        enhancer: true,
        extra_bass: false,
    };

    const cinema = profiles?.cinema ?? {
        name: "Salle de cinéma",
        volume_pct: 60,
        volume_raw: 95,
        dialog_lift: 1,
        dialog_level: 1,
        movie_sound_program: "straight",
        series_sound_program: "spectacle",
        music_sound_program: "7ch_stereo",
        adaptive_drc: false,
        enhancer: false,
        extra_bass: true,
    };

    if (isLoading) {
        return <div className="h-32 rounded-lg bg-muted/15 animate-pulse" />;
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ProfileCard
                roomKey="salon"
                icon="🛋️"
                title="Salon"
                profile={salon}
                onSave={(p) =>
                    saveMutation.mutate(
                        { room: "salon", profile: p },
                        { onSuccess: () => toast.success("Profil Salon sauvegardé !") },
                    )
                }
            />
            <ProfileCard
                roomKey="cinema"
                icon="🍿"
                title="Salle de Cinéma"
                profile={cinema}
                onSave={(p) =>
                    saveMutation.mutate(
                        { room: "cinema", profile: p },
                        { onSuccess: () => toast.success("Profil Salle de Cinéma sauvegardé !") },
                    )
                }
            />
        </div>
    );
}

function ProfileCard({
    roomKey,
    icon,
    title,
    profile,
    onSave,
}: {
    roomKey: string;
    icon: string;
    title: string;
    profile: any;
    onSave: (p: any) => void;
}) {
    const [volRaw, setVolRaw] = useState(profile.volume_raw ?? 65);
    const [dialogLift, setDialogLift] = useState(profile.dialog_lift ?? 1);
    const [movieProg, setMovieProg] = useState(profile.movie_sound_program ?? "straight");
    const [seriesProg, setSeriesProg] = useState(profile.series_sound_program ?? "drama");
    const [drc, setDrc] = useState(!!profile.adaptive_drc);
    const [extraBass, setExtraBass] = useState(!!profile.extra_bass);

    const handleSave = () => {
        onSave({
            volume_raw: Number(volRaw),
            volume_pct: Math.round((volRaw / 161) * 100),
            dialog_lift: Number(dialogLift),
            movie_sound_program: movieProg,
            series_sound_program: seriesProg,
            adaptive_drc: drc,
            extra_bass: extraBass,
        });
    };

    return (
        <div className="rounded-lg border border-white/10 bg-black/20 p-4 space-y-3">
            <div className="flex items-center justify-between">
                <span className="font-semibold text-sm flex items-center gap-1.5">
                    {icon} {title}
                </span>
                <Button size="sm" variant="secondary" onClick={handleSave} className="h-7 text-xs">
                    Sauvegarder
                </Button>
            </div>

            <div className="space-y-2 text-xs">
                <div className="space-y-1">
                    <div className="flex justify-between text-muted-foreground">
                        <span>Volume cible (ampli)</span>
                        <span className="tabular-nums font-mono">{Math.round((volRaw / 161) * 100)}%</span>
                    </div>
                    <input
                        type="range"
                        min={20}
                        max={120}
                        value={volRaw}
                        onChange={(e) => setVolRaw(Number(e.target.value))}
                        className="w-full accent-purple-500 h-1.5 cursor-pointer"
                    />
                </div>

                <div className="grid grid-cols-2 gap-2 pt-1">
                    <div>
                        <Label className="text-[11px] text-muted-foreground">Prog. Son (Films)</Label>
                        <Input
                            value={movieProg}
                            onChange={(e) => setMovieProg(e.target.value)}
                            className="h-7 text-xs border-white/10 bg-transparent"
                            placeholder="straight / sci-fi"
                        />
                    </div>
                    <div>
                        <Label className="text-[11px] text-muted-foreground">Prog. Son (Séries)</Label>
                        <Input
                            value={seriesProg}
                            onChange={(e) => setSeriesProg(e.target.value)}
                            className="h-7 text-xs border-white/10 bg-transparent"
                            placeholder="drama / spectacle"
                        />
                    </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                    <Label className="text-[11px] text-muted-foreground">Rehaussement Voix (0-5)</Label>
                    <Input
                        type="number"
                        min={0}
                        max={5}
                        value={dialogLift}
                        onChange={(e) => setDialogLift(Number(e.target.value))}
                        className="h-7 w-16 text-xs border-white/10 bg-transparent text-right"
                    />
                </div>

                <div className="flex items-center justify-between pt-1">
                    <span className="text-muted-foreground">Mode Nuit (DRC Adaptatif)</span>
                    <Button
                        size="sm"
                        variant={drc ? "default" : "outline"}
                        className={`h-6 text-[11px] px-2 ${drc ? "bg-amber-600 hover:bg-amber-500 text-white" : "border-white/10"}`}
                        onClick={() => setDrc(!drc)}
                    >
                        {drc ? "Activé" : "Désactivé"}
                    </Button>
                </div>

                <div className="flex items-center justify-between pt-1">
                    <span className="text-muted-foreground">Extra Bass (Subwoofer Boost)</span>
                    <Button
                        size="sm"
                        variant={extraBass ? "default" : "outline"}
                        className={`h-6 text-[11px] px-2 ${extraBass ? "bg-purple-600 hover:bg-purple-500 text-white" : "border-white/10"}`}
                        onClick={() => setExtraBass(!extraBass)}
                    >
                        {extraBass ? "Activé" : "Désactivé"}
                    </Button>
                </div>
            </div>
        </div>
    );
}
