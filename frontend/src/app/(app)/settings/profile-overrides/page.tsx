"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shared/empty-state";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import {
    Target,
    Trash2,
    Plus,
    Film,
    Tv,
    Search,
} from "lucide-react";
import {
    useProfileOverrides,
    useAvailableProfiles,
    useCreateOverride,
    useDeleteOverride,
} from "@/hooks/use-profile-overrides";
import { useServices } from "@/hooks/use-services";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

export default function ProfileOverridesPage() {
    const { data: overrides, isLoading } = useProfileOverrides();
    const { data: services } = useServices();
    const deleteOverride = useDeleteOverride();
    const [search, setSearch] = useState("");
    const [showAdd, setShowAdd] = useState(false);

    const arrServices = services?.filter(
        (s) => ["sonarr", "radarr"].includes(s.type.toLowerCase())
    ) ?? [];

    const filtered = (overrides ?? []).filter((o) =>
        o.title.toLowerCase().includes(search.toLowerCase())
    );

    if (isLoading) {
        return (
            <>
                <Header title="Profils par média" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    return (
        <>
            <Header title="Profils TRaSH par média" />
            <div className="p-6 max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between gap-4">
                    <div className="relative flex-1 max-w-sm">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                        <Input
                            placeholder="Chercher un titre..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-9"
                        />
                    </div>
                    <Button onClick={() => setShowAdd(!showAdd)} className="gap-2">
                        <Plus className="h-4 w-4" />
                        Ajouter un override
                    </Button>
                </div>

                {/* Add Form */}
                <AnimatePresence>
                    {showAdd && (
                        <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                        >
                            <AddOverrideForm
                                services={arrServices}
                                onDone={() => setShowAdd(false)}
                            />
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* List */}
                {filtered.length === 0 ? (
                    <EmptyState
                        icon={Target}
                        title="Aucun override"
                        description="Tous les médias utilisent le profil TRaSH par défaut. Ajoutez un override pour personnaliser un titre spécifique."
                    />
                ) : (
                    <div className="grid gap-3">
                        {filtered.map((o, i) => (
                            <motion.div
                                key={o.id}
                                initial={{ opacity: 0, y: 8 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: i * 0.03 }}
                            >
                                <Card className="hover:bg-muted/30 transition-colors">
                                    <CardContent className="flex items-center gap-4 p-4">
                                        <div className={cn(
                                            "rounded-full p-2 shrink-0",
                                            o.media_type === "series"
                                                ? "bg-blue-500/10"
                                                : "bg-purple-500/10"
                                        )}>
                                            {o.media_type === "series" ? (
                                                <Tv className="h-4 w-4 text-blue-400" />
                                            ) : (
                                                <Film className="h-4 w-4 text-purple-400" />
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-medium truncate">
                                                {o.title}
                                            </p>
                                            <div className="flex gap-2 mt-1">
                                                <Badge variant="outline" className="text-xs">
                                                    {o.profile_name.replace(/-/g, " ")}
                                                </Badge>
                                                {o.note && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {o.note}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="shrink-0 text-muted-foreground hover:text-red-400"
                                            onClick={() => deleteOverride.mutate(o.id)}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </CardContent>
                                </Card>
                            </motion.div>
                        ))}
                    </div>
                )}
            </div>
        </>
    );
}

// ── Add Form Component ──────────────────────────────────────

interface ServiceItem {
    id: number;
    name: string;
    type: string;
}

function AddOverrideForm({
    services,
    onDone,
}: {
    services: ServiceItem[];
    onDone: () => void;
}) {
    const createOverride = useCreateOverride();
    const [selectedService, setSelectedService] = useState<number | null>(
        services.length > 0 ? services[0].id : null
    );
    const selectedType = services.find(s => s.id === selectedService)?.type.toLowerCase() ?? "sonarr";
    const { data: profiles } = useAvailableProfiles(selectedType);

    const [title, setTitle] = useState("");
    const [externalId, setExternalId] = useState("");
    const [profile, setProfile] = useState("");
    const [mediaType, setMediaType] = useState<"series" | "movie">(
        selectedType === "sonarr" ? "series" : "movie"
    );
    const [note, setNote] = useState("");

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedService || !title || !externalId || !profile) return;

        await createOverride.mutateAsync({
            media_type: mediaType,
            external_id: parseInt(externalId),
            title,
            profile_name: profile,
            service_id: selectedService,
            note: note || undefined,
        });
        onDone();
    };

    return (
        <Card>
            <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                    <Plus className="h-4 w-4" />
                    Nouvel override de profil
                </CardTitle>
            </CardHeader>
            <CardContent>
                <form onSubmit={handleSubmit} className="grid gap-4 sm:grid-cols-2">
                    {/* Service */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">
                            Service
                        </label>
                        <select
                            value={selectedService ?? ""}
                            onChange={(e) => {
                                const id = parseInt(e.target.value);
                                setSelectedService(id);
                                const svc = services.find(s => s.id === id);
                                setMediaType(svc?.type.toLowerCase() === "sonarr" ? "series" : "movie");
                            }}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                            {services.map((s) => (
                                <option key={s.id} value={s.id}>
                                    {s.name} ({s.type})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Title */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">
                            Titre du média
                        </label>
                        <Input
                            placeholder="Ex: Attack on Titan"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            required
                        />
                    </div>

                    {/* External ID */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">
                            ID {mediaType === "series" ? "Sonarr" : "Radarr"}
                        </label>
                        <Input
                            type="number"
                            placeholder="Ex: 42"
                            value={externalId}
                            onChange={(e) => setExternalId(e.target.value)}
                            required
                        />
                    </div>

                    {/* Profile */}
                    <div>
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">
                            Profil TRaSH
                        </label>
                        <select
                            value={profile}
                            onChange={(e) => setProfile(e.target.value)}
                            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                            required
                        >
                            <option value="">Choisir un profil...</option>
                            {(profiles ?? []).map((p) => (
                                <option key={p.filename} value={p.filename}>
                                    {p.display_name}
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Note */}
                    <div className="sm:col-span-2">
                        <label className="text-xs font-medium text-muted-foreground mb-1 block">
                            Note (optionnel)
                        </label>
                        <Input
                            placeholder="Ex: Anime → 1080p seulement"
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                        />
                    </div>

                    {/* Buttons */}
                    <div className="sm:col-span-2 flex justify-end gap-2">
                        <Button type="button" variant="ghost" onClick={onDone}>
                            Annuler
                        </Button>
                        <Button type="submit" disabled={createOverride.isPending}>
                            {createOverride.isPending ? "Création..." : "Créer l'override"}
                        </Button>
                    </div>
                </form>
            </CardContent>
        </Card>
    );
}
