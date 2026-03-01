"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { EmptyState } from "@/components/shared/empty-state";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
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
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import {
    MessageSquarePlus,
    Trash2,
    Film,
    Tv,
    Plus,
    Loader2,
    Search,
    Clock,
    CheckCircle,
    XCircle,
    Download,
} from "lucide-react";
import {
    useRequests,
    useCreateRequest,
    useDeleteRequest,
} from "@/hooks/use-requests";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useToast } from "@/components/ui/use-toast";

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: any }> = {
    requested: { label: "Demandé", color: "bg-blue-500", icon: Clock },
    searching: { label: "Recherche", color: "bg-yellow-500", icon: Search },
    downloading: { label: "Téléchargement", color: "bg-purple-500", icon: Download },
    available: { label: "Disponible", color: "bg-green-500", icon: CheckCircle },
    failed: { label: "Échoué", color: "bg-red-500", icon: XCircle },
};

export default function RequestsPage() {
    const { data, isLoading } = useRequests();
    const createMutation = useCreateRequest();
    const deleteMutation = useDeleteRequest();
    const { toast } = useToast();

    const [dialogOpen, setDialogOpen] = useState(false);
    const [title, setTitle] = useState("");
    const [type, setType] = useState("movie");
    const [year, setYear] = useState("");
    const [tmdbId, setTmdbId] = useState("");

    const handleSubmit = async () => {
        if (!title.trim()) return;

        try {
            await createMutation.mutateAsync({
                title: title.trim(),
                type,
                year: year ? parseInt(year) : null,
                tmdb_id: tmdbId ? parseInt(tmdbId) : null,
            });
            toast({
                title: "Requête envoyée",
                description: `« ${title} » a été ajouté et envoyé à ${type === "movie" ? "Radarr" : "Sonarr"}`,
            });
            setTitle("");
            setYear("");
            setTmdbId("");
            setDialogOpen(false);
        } catch {
            toast({
                title: "Erreur",
                description: "Impossible de créer la requête",
                variant: "destructive",
            });
        }
    };

    const handleDelete = async (id: number) => {
        try {
            await deleteMutation.mutateAsync(id);
            toast({ title: "Requête supprimée" });
        } catch {
            toast({
                title: "Erreur",
                description: "Impossible de supprimer la requête",
                variant: "destructive",
            });
        }
    };

    if (isLoading) {
        return (
            <>
                <Header title="Requêtes" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    return (
        <>
            <Header title="Requêtes" />
            <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                    <div>
                        <h2 className="text-2xl font-bold tracking-tight">
                            Requêtes média
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            Demandez des films ou des séries à ajouter automatiquement
                        </p>
                    </div>

                    <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="h-4 w-4 mr-2" />
                                Nouvelle requête
                            </Button>
                        </DialogTrigger>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Ajouter un média</DialogTitle>
                                <DialogDescription>
                                    Le média sera automatiquement ajouté à Radarr ou Sonarr et la
                                    recherche démarrera.
                                </DialogDescription>
                            </DialogHeader>

                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <Label htmlFor="req-title">Titre</Label>
                                    <Input
                                        id="req-title"
                                        placeholder="Ex: Dune Part Two"
                                        value={title}
                                        onChange={(e) => setTitle(e.target.value)}
                                    />
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Type</Label>
                                        <Select value={type} onValueChange={setType}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="movie">Film</SelectItem>
                                                <SelectItem value="series">Série</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label htmlFor="req-year">Année</Label>
                                        <Input
                                            id="req-year"
                                            placeholder="2024"
                                            value={year}
                                            onChange={(e) => setYear(e.target.value)}
                                        />
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="req-tmdb">TMDB ID (optionnel)</Label>
                                    <Input
                                        id="req-tmdb"
                                        placeholder="ex: 693134"
                                        value={tmdbId}
                                        onChange={(e) => setTmdbId(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Si fourni, le média sera recherché par TMDB ID pour plus de
                                        précision
                                    </p>
                                </div>
                            </div>

                            <DialogFooter>
                                <Button
                                    variant="outline"
                                    onClick={() => setDialogOpen(false)}
                                >
                                    Annuler
                                </Button>
                                <Button
                                    onClick={handleSubmit}
                                    disabled={!title.trim() || createMutation.isPending}
                                >
                                    {createMutation.isPending ? (
                                        <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                    ) : (
                                        <Plus className="h-4 w-4 mr-2" />
                                    )}
                                    Ajouter
                                </Button>
                            </DialogFooter>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Stats */}
                {data && data.total > 0 && (
                    <div className="flex gap-3">
                        {Object.entries(STATUS_CONFIG).map(([key, cfg]) => {
                            const count = data.items.filter((r) => r.status === key).length;
                            if (count === 0) return null;
                            return (
                                <Badge key={key} variant="outline" className="gap-1.5">
                                    <span className={cn("h-2 w-2 rounded-full", cfg.color)} />
                                    {cfg.label}: {count}
                                </Badge>
                            );
                        })}
                    </div>
                )}

                {/* Requests list */}
                {!data || data.items.length === 0 ? (
                    <EmptyState
                        icon={MessageSquarePlus}
                        title="Aucune requête"
                        description="Demandez des films ou séries — ils seront automatiquement ajoutés à vos services"
                    />
                ) : (
                    <div className="space-y-3">
                        {data.items.map((req, i) => {
                            const statusCfg = STATUS_CONFIG[req.status] || STATUS_CONFIG.requested;
                            const StatusIcon = statusCfg.icon;

                            return (
                                <motion.div
                                    key={req.id}
                                    initial={{ opacity: 0, y: 5 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.03 }}
                                >
                                    <Card>
                                        <CardContent className="p-4 flex items-center gap-4">
                                            {/* Poster thumbnail */}
                                            <div className="w-12 h-16 rounded-md overflow-hidden bg-muted shrink-0">
                                                {req.poster_url ? (
                                                    <img
                                                        src={req.poster_url}
                                                        alt=""
                                                        className="w-full h-full object-cover"
                                                    />
                                                ) : (
                                                    <div className="w-full h-full flex items-center justify-center">
                                                        {req.type === "movie" ? (
                                                            <Film className="h-5 w-5 text-muted-foreground/30" />
                                                        ) : (
                                                            <Tv className="h-5 w-5 text-muted-foreground/30" />
                                                        )}
                                                    </div>
                                                )}
                                            </div>

                                            {/* Info */}
                                            <div className="flex-1 min-w-0">
                                                <p className="font-semibold truncate">{req.title}</p>
                                                <div className="flex items-center gap-2 mt-1">
                                                    {req.year && (
                                                        <span className="text-xs text-muted-foreground">
                                                            {req.year}
                                                        </span>
                                                    )}
                                                    <Badge
                                                        variant="outline"
                                                        className="text-[10px] capitalize"
                                                    >
                                                        {req.type === "movie" ? "Film" : "Série"}
                                                    </Badge>
                                                    <span className="text-xs text-muted-foreground">
                                                        → {req.target_service}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Status */}
                                            <div className="flex items-center gap-2 shrink-0">
                                                <Badge
                                                    variant="outline"
                                                    className="gap-1.5 capitalize"
                                                >
                                                    <StatusIcon className="h-3 w-3" />
                                                    {statusCfg.label}
                                                </Badge>
                                            </div>

                                            {/* Date */}
                                            <span className="text-xs text-muted-foreground shrink-0 hidden md:block">
                                                {req.requested_at
                                                    ? new Date(req.requested_at).toLocaleDateString(
                                                        "fr-FR",
                                                        {
                                                            day: "numeric",
                                                            month: "short",
                                                            hour: "2-digit",
                                                            minute: "2-digit",
                                                        }
                                                    )
                                                    : "—"}
                                            </span>

                                            {/* Delete */}
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="shrink-0 text-muted-foreground hover:text-destructive"
                                                onClick={() => handleDelete(req.id)}
                                                disabled={deleteMutation.isPending}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                )}
            </div>
        </>
    );
}
