"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/shared/empty-state";
import { Cast, Tv, Speaker, Trash2, Loader2, Radar, CheckCircle2, XCircle, Server } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
    useCastDevices,
    useCastDiscover,
    useDeleteCastDevice,
    useJellyfinConfig,
    useSetJellyfin,
    useTestJellyfin,
} from "@/hooks/use-cast";

export default function CastSettingsPage() {
    const { data: devices, isLoading } = useCastDevices();
    const discover = useCastDiscover();
    const del = useDeleteCastDevice();
    const { data: jf } = useJellyfinConfig();
    const setJf = useSetJellyfin();
    const testJf = useTestJellyfin();

    const [url, setUrl] = useState("http://192.168.2.3:8097");
    const [apiKey, setApiKey] = useState("");
    const [jfResult, setJfResult] = useState<null | { ok: boolean; label: string }>(null);

    useEffect(() => {
        if (jf?.url) setUrl(jf.url);
    }, [jf?.url]);

    return (
        <>
            <Header title="Cast" />
            <motion.div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                {/* Jellyfin */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2 text-base">
                            <Server className="h-5 w-5 text-sky-400" /> Jellyfin (transcodage)
                        </CardTitle>
                        <CardDescription>
                            Jellyfin transcode tes fichiers pour qu&apos;ils soient lisibles par les Chromecast.
                            {jf?.configured && <span className="ml-1 text-emerald-400">· Configuré</span>}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                            <div className="space-y-1">
                                <Label className="text-xs">URL</Label>
                                <Input value={url} onChange={(e) => setUrl(e.target.value)} className="border-white/10 bg-transparent font-mono text-sm" />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Clé API {jf?.configured && <span className="text-muted-foreground">(laisser vide pour garder)</span>}</Label>
                                <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} type="password" placeholder="••••••••" className="border-white/10 bg-transparent font-mono text-sm" />
                            </div>
                        </div>
                        <div className="flex flex-wrap gap-2 items-center">
                            <Button
                                disabled={setJf.isPending}
                                onClick={() =>
                                    setJf.mutate(
                                        { url, api_key: apiKey, name: "Jellyfin" },
                                        {
                                            onSuccess: () => { toast.success("Jellyfin enregistré."); setApiKey(""); },
                                            onError: (e) => toast.error("Échec : " + e.message),
                                        },
                                    )
                                }
                            >
                                {setJf.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                                Enregistrer
                            </Button>
                            <Button
                                variant="outline"
                                className="border-white/10"
                                disabled={testJf.isPending}
                                onClick={() =>
                                    testJf.mutate(undefined, {
                                        onSuccess: (r) => setJfResult(r.ok ? { ok: true, label: `${r.server} ${r.version}` } : { ok: false, label: r.detail || "injoignable" }),
                                        onError: (e) => setJfResult({ ok: false, label: e.message }),
                                    })
                                }
                            >
                                {testJf.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                                Tester
                            </Button>
                            {jfResult && (
                                <span className={`text-xs flex items-center gap-1 ${jfResult.ok ? "text-emerald-400" : "text-red-400"}`}>
                                    {jfResult.ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
                                    {jfResult.label}
                                </span>
                            )}
                        </div>
                    </CardContent>
                </Card>

                {/* Devices */}
                <Card className="bg-card/40 border-border/50">
                    <CardHeader>
                        <div className="flex items-center justify-between gap-2">
                            <div>
                                <CardTitle className="flex items-center gap-2 text-base">
                                    <Cast className="h-5 w-5 text-sky-400" /> Appareils Cast
                                </CardTitle>
                                <CardDescription>Chromecast, Google TV et Nest détectés sur ton réseau.</CardDescription>
                            </div>
                            <Button
                                variant="outline"
                                size="sm"
                                className="border-white/10 shrink-0"
                                disabled={discover.isPending}
                                onClick={() =>
                                    discover.mutate(undefined, {
                                        onSuccess: (list) => toast.success(`${list.length} appareil(s) détecté(s).`),
                                        onError: (e) => toast.error("Scan échoué : " + e.message),
                                    })
                                }
                            >
                                {discover.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Radar className="h-4 w-4 mr-2" />}
                                Scanner
                            </Button>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {isLoading ? (
                            <div className="h-16 rounded-lg bg-muted/15 animate-pulse" />
                        ) : (devices?.length ?? 0) === 0 ? (
                            <EmptyState icon={Cast} title="Aucun appareil" description="Lance un scan pour détecter tes Chromecast." />
                        ) : (
                            devices!.map((d) => (
                                <div key={d.id} className="flex items-center gap-3 rounded-lg border border-border/50 bg-card/40 p-3">
                                    {d.video_capable ? <Tv className="h-5 w-5 text-sky-400 shrink-0" /> : <Speaker className="h-5 w-5 text-muted-foreground shrink-0" />}
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-medium truncate">{d.name}</p>
                                        <p className="text-xs text-muted-foreground font-mono truncate">{d.ip}</p>
                                    </div>
                                    <Badge variant="outline" className={`text-[10px] ${d.video_capable ? "border-sky-500/30 text-sky-300" : "border-white/10 text-muted-foreground"}`}>
                                        {d.video_capable ? "Vidéo" : "Audio"}
                                    </Badge>
                                    <Button size="icon" variant="ghost" className="h-8 w-8 text-muted-foreground hover:text-red-400" onClick={() => del.mutate(d.id, { onSuccess: () => toast.success("Appareil retiré.") })}>
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            ))
                        )}
                    </CardContent>
                </Card>
            </motion.div>
        </>
    );
}
