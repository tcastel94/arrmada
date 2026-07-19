"use client";

import { useState, useEffect } from "react";
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
import { apiFetch } from "@/lib/api-client";

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
    const [posterUrl, setPosterUrl] = useState("");
    const [searchResults, setSearchResults] = useState<any[]>([]);
    const [isSearching, setIsSearching] = useState(false);

    useEffect(() => {
        if (title.trim().length < 2) {
            setSearchResults([]);
            return;
        }

        const delayDebounce = setTimeout(async () => {
            setIsSearching(true);
            try {
                const results = await apiFetch(`/api/requests/lookup?q=${encodeURIComponent(title.trim())}&type=${type}`);
                setSearchResults(results);
            } catch {
                setSearchResults([]);
            } finally {
                setIsSearching(false);
            }
        }, 500);

        return () => clearTimeout(delayDebounce);
    }, [title, type]);

    const handleSubmit = async () => {
        if (!title.trim()) return;

        try {
            await createMutation.mutateAsync({
                title: title.trim(),
                type,
                year: year ? parseInt(year) : null,
                tmdb_id: tmdbId ? parseInt(tmdbId) : null,
                poster_url: posterUrl || null,
            });
            toast({
                title: "Requête envoyée",
                description: `« ${title} » a été ajouté et envoyé à ${type === "movie" ? "Radarr" : "Sonarr"}`,
            });
            setTitle("");
            setYear("");
            setTmdbId("");
            setPosterUrl("");
            setSearchResults([]);
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

                    <Dialog open={dialogOpen} onOpenChange={(open) => {
                        setDialogOpen(open);
                        if (!open) {
                            setTitle("");
                            setYear("");
                            setTmdbId("");
                            setPosterUrl("");
                            setSearchResults([]);
                        }
                    }}>
                        <DialogTrigger asChild>
                            <Button>
                                <Plus className="h-4 w-4 mr-2" />
                                Nouvelle requête
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-md">
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
                                        autoComplete="off"
                                    />
                                </div>

                                {/* Autocomplete Results */}
                                {title.trim().length >= 2 && searchResults.length > 0 && (
                                    <div className="border rounded-md max-h-56 overflow-y-auto divide-y bg-popover text-popover-foreground shadow-lg">
                                        {isSearching ? (
                                            <div className="p-3 text-xs text-muted-foreground flex items-center justify-center gap-2">
                                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                                Recherche en cours...
                                            </div>
                                        ) : (
                                            searchResults.map((item) => (
                                                <button
                                                    key={item.tmdb_id || item.title}
                                                    type="button"
                                                    className="w-full text-left p-2.5 hover:bg-accent hover:text-accent-foreground text-xs flex items-start gap-3 transition-colors"
                                                    onClick={() => {
                                                        setTitle(item.title);
                                                        setYear(item.year ? item.year.toString() : "");
                                                        setTmdbId(item.tmdb_id ? item.tmdb_id.toString() : "");
                                                        setPosterUrl(item.poster_url || "");
                                                        setSearchResults([]);
                                                    }}
                                                >
                                                    {item.poster_url ? (
                                                        <img
                                                            src={item.poster_url}
                                                            alt=""
                                                            className="w-9 h-12 object-cover rounded bg-muted shrink-0"
                                                        />
                                                    ) : (
                                                        <div className="w-9 h-12 bg-muted rounded shrink-0 flex items-center justify-center">
                                                            {type === "movie" ? <Film className="h-4 w-4 text-muted-foreground/40" /> : <Tv className="h-4 w-4 text-muted-foreground/40" />}
                                                        </div>
                                                    )}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="font-semibold flex items-center justify-between">
                                                            <span className="truncate pr-1">{item.title}</span>
                                                            {item.year && <span className="text-muted-foreground shrink-0 text-[10px]">{item.year}</span>}
                                                        </div>
                                                        {item.overview && (
                                                            <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">
                                                                {item.overview}
                                                            </p>
                                                        )}
                                                        <div className="text-[9px] text-muted-foreground mt-1 flex items-center justify-between">
                                                            <div>
                                                                <span className="font-medium mr-0.5">{type === "movie" ? "TMDB ID:" : "TVDB ID:"}</span>
                                                                <span className="bg-muted px-1 py-0.5 rounded">{item.tmdb_id || "N/A"}</span>
                                                            </div>
                                                            {item.tmdb_id && (
                                                                <a
                                                                    href={type === "movie" ? `https://www.themoviedb.org/movie/${item.tmdb_id}` : `https://thetvdb.com/dereferrer/series/${item.tmdb_id}`}
                                                                    target="_blank"
                                                                    rel="noreferrer"
                                                                    className="text-primary hover:underline font-semibold"
                                                                    onClick={(e) => e.stopPropagation()}
                                                                >
                                                                    Voir fiche ↗
                                                                </a>
                                                            )}
                                                        </div>
                                                    </div>
                                                </button>
                                            ))
                                        )}
                                    </div>
                                )}
                                {title.trim().length >= 2 && searchResults.length === 0 && isSearching && (
                                    <div className="border rounded-md p-3 text-xs text-muted-foreground flex items-center justify-center gap-2 bg-popover shadow-lg">
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        Recherche en cours...
                                    </div>
                                )}

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Type</Label>
                                        <Select value={type} onValueChange={(val) => {
                                            setType(val);
                                            setSearchResults([]);
                                            setYear("");
                                            setTmdbId("");
                                            setPosterUrl("");
                                        }}>
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
                                    <Label htmlFor="req-tmdb">
                                        {type === "movie" ? "TMDB ID" : "TVDB ID"} (optionnel)
                                    </Label>
                                    <Input
                                        id="req-tmdb"
                                        placeholder={type === "movie" ? "ex: 693134" : "ex: 79286"}
                                        value={tmdbId}
                                        onChange={(e) => setTmdbId(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        {type === "movie" 
                                            ? "Si fourni, le média sera recherché par TMDB ID pour plus de précision"
                                            : "Si fourni, la série sera recherchée par TVDB ID pour plus de précision"
                                        }
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
                                                    <span className={cn("h-2 w-2 rounded-full", statusCfg.color)} />
                                                    <StatusIcon className="h-3 w-3 text-muted-foreground" />
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
