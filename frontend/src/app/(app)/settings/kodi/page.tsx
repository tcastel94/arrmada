"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { MonitorPlay, Search, Trash2, CheckCircle2 } from "lucide-react";
import { motion } from "framer-motion";

interface KodiInstance {
    id?: number;
    name: string;
    url: string;
    is_enabled: boolean;
    api_key?: string; // stored as username:password
}

export default function KodiSettingsPage() {
    const [savedKodis, setSavedKodis] = useState<KodiInstance[]>([]);
    const [discoveredKodis, setDiscoveredKodis] = useState<KodiInstance[]>([]);
    const [isDiscovering, setIsDiscovering] = useState(false);
    
    // Form for manual add
    const [name, setName] = useState("Kodi Salon");
    const [url, setUrl] = useState("http://192.168.1.10:8080");
    const [auth, setAuth] = useState("kodi:kodi");

    const loadSettings = async () => {
        try {
            const res = await apiFetch("/api/kodi/settings");
            if (res.ok) setSavedKodis(await res.json());
        } catch (e) {}
    };

    useEffect(() => {
        loadSettings();
    }, []);

    const handleDiscover = async () => {
        setIsDiscovering(true);
        try {
            const res = await apiFetch("/api/kodi/discover");
            if (res.ok) setDiscoveredKodis(await res.json());
        } catch (e) {}
        setIsDiscovering(false);
    };

    const handleAdd = async (kodi: KodiInstance) => {
        try {
            const res = await apiFetch("/api/kodi/settings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ...kodi, is_enabled: true })
            });
            if (res.ok) {
                alert("Kodi ajouté !");
                loadSettings();
            }
        } catch (e) {}
    };

    const handleDelete = async (id: number) => {
        try {
            await apiFetch(`/api/kodi/settings/${id}`, { method: "DELETE" });
            loadSettings();
        } catch (e) {}
    };

    return (
        <>
            <Header title="Paramètres Kodi" />
            <motion.div className="p-4 md:p-6 space-y-6 max-w-4xl mx-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                
                <Card className="bg-card/40 border-0 ring-1 ring-white/5">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <MonitorPlay className="h-5 w-5 text-sky-400" />
                            Instances Sauvegardées
                        </CardTitle>
                        <CardDescription>
                            Kodi sur lesquels la mise à jour de la médiathèque sera lancée.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {savedKodis.length === 0 ? (
                            <p className="text-sm text-muted-foreground">Aucune instance Kodi configurée.</p>
                        ) : (
                            savedKodis.map(k => (
                                <div key={k.id} className="flex items-center justify-between p-3 rounded-lg bg-black/20 ring-1 ring-white/5">
                                    <div>
                                        <p className="font-medium text-sm flex items-center gap-2">
                                            {k.name}
                                            <CheckCircle2 className="h-4 w-4 text-green-500" />
                                        </p>
                                        <p className="text-xs text-muted-foreground">{k.url}</p>
                                    </div>
                                    <Button variant="ghost" size="icon" onClick={() => k.id && handleDelete(k.id)}>
                                        <Trash2 className="h-4 w-4 text-red-400" />
                                    </Button>
                                </div>
                            ))
                        )}
                    </CardContent>
                </Card>

                <div className="grid md:grid-cols-2 gap-6">
                    <Card className="bg-card/40 border-0 ring-1 ring-white/5">
                        <CardHeader>
                            <CardTitle className="text-base flex items-center gap-2">
                                <Search className="h-4 w-4" />
                                Découverte Automatique (mDNS)
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <Button onClick={handleDiscover} disabled={isDiscovering} className="w-full">
                                {isDiscovering ? "Recherche en cours..." : "Scanner le réseau"}
                            </Button>
                            
                            {discoveredKodis.length > 0 && (
                                <div className="space-y-2 mt-4">
                                    {discoveredKodis.map((k, i) => (
                                        <div key={i} className="flex items-center justify-between p-2 rounded bg-black/20 text-sm">
                                            <span>{k.name} ({k.url})</span>
                                            <Button size="sm" variant="outline" onClick={() => handleAdd({ ...k, api_key: "kodi:kodi" })}>
                                                Ajouter
                                            </Button>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="bg-card/40 border-0 ring-1 ring-white/5">
                        <CardHeader>
                            <CardTitle className="text-base">Ajout Manuel</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="space-y-2">
                                <Label>Nom de l'instance</Label>
                                <Input value={name} onChange={e => setName(e.target.value)} className="bg-black/20 border-white/10" />
                            </div>
                            <div className="space-y-2">
                                <Label>URL de l'API web (ex: http://ip:8080)</Label>
                                <Input value={url} onChange={e => setUrl(e.target.value)} className="bg-black/20 border-white/10" />
                            </div>
                            <div className="space-y-2">
                                <Label>Identifiants (user:pass)</Label>
                                <Input value={auth} onChange={e => setAuth(e.target.value)} className="bg-black/20 border-white/10" />
                            </div>
                            <Button className="w-full" onClick={() => handleAdd({ name, url, is_enabled: true, api_key: auth })}>
                                Ajouter manuellement
                            </Button>
                        </CardContent>
                    </Card>
                </div>
            </motion.div>
        </>
    );
}
