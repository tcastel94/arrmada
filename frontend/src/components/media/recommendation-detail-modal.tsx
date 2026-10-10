"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Star,
    Film,
    Tv,
    Clock,
    User,
    Play,
    Plus,
    Check,
    ExternalLink,
    Loader2,
    Sparkles,
} from "lucide-react";
import { useCreateRequest } from "@/hooks/use-requests";
import { toast } from "sonner";
import Link from "next/link";

export interface TMDBDetailResponse {
    tmdb_id: number;
    title: string;
    original_title: string;
    type: string;
    year: string | null;
    release_date: string | null;
    overview: string;
    rating: number | null;
    vote_count: number;
    popularity: number;
    runtime: number | null;
    poster_url: string | null;
    backdrop_url: string | null;
    genres: string[];
    cast: { name: string; character: string; profile_path: string | null }[];
    director: string | null;
    trailer_key: string | null;
    in_library: boolean;
    library_item: { id: number; type: string } | null;
}

export interface RecommendationDetailModalProps {
    tmdbId: number | null;
    mediaType?: string;
    isOpen: boolean;
    onClose: () => void;
}

export function RecommendationDetailModal({
    tmdbId,
    mediaType = "movie",
    isOpen,
    onClose,
}: RecommendationDetailModalProps) {
    const [isPlayingTrailer, setIsPlayingTrailer] = useState(false);
    const createRequest = useCreateRequest();

    const { data: detail, isLoading } = useQuery<TMDBDetailResponse>({
        queryKey: ["tmdb-detail", mediaType, tmdbId],
        queryFn: () => apiFetch(`/api/recommendations/details/${mediaType}/${tmdbId}`),
        enabled: isOpen && !!tmdbId,
    });

    const handleAddRequest = async () => {
        if (!detail) return;
        try {
            await createRequest.mutateAsync({
                title: detail.title,
                type: detail.type,
                tmdb_id: detail.tmdb_id,
                year: detail.year ? parseInt(detail.year, 10) : null,
                poster_url: detail.poster_url,
            });
            toast.success(`Demandé : ${detail.title} a été ajouté aux requêtes !`);
        } catch (err: any) {
            toast.error(err.message || "Erreur lors de l'ajout de la requête.");
        }
    };

    if (!isOpen || !tmdbId) return null;

    return (
        <Dialog open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
            <DialogContent className="max-w-3xl p-0 overflow-hidden bg-zinc-950/95 border-zinc-800 text-white shadow-2xl backdrop-blur-xl rounded-2xl">
                <DialogHeader className="sr-only">
                    <DialogTitle>{detail?.title || "Détails du média"}</DialogTitle>
                </DialogHeader>

                {isLoading ? (
                    <div className="p-8 space-y-4">
                        <Skeleton className="h-60 w-full rounded-xl bg-zinc-800/50" />
                        <Skeleton className="h-8 w-1/2 bg-zinc-800/50" />
                        <Skeleton className="h-20 w-full bg-zinc-800/50" />
                    </div>
                ) : detail ? (
                    <div className="relative max-h-[85vh] overflow-y-auto custom-scrollbar">
                        {/* Backdrop Hero Header */}
                        <div className="relative aspect-[16/9] sm:aspect-[21/9] w-full overflow-hidden bg-zinc-900">
                            {detail.backdrop_url ? (
                                <img
                                    src={detail.backdrop_url}
                                    alt={detail.title}
                                    className="w-full h-full object-cover opacity-40"
                                />
                            ) : (
                                <div className="w-full h-full bg-gradient-to-br from-indigo-900/30 to-purple-900/30" />
                            )}
                            <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/60 to-transparent" />

                            {/* Floating Actions on Backdrop */}
                            <div className="absolute bottom-4 left-6 right-6 flex items-end justify-between gap-4">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <Badge className="bg-primary/80 text-white text-xs">
                                            {detail.type === "movie" ? "Film" : "Série"}
                                        </Badge>
                                        {detail.year && (
                                            <span className="text-xs text-zinc-300 font-medium">
                                                {detail.year}
                                            </span>
                                        )}
                                        {detail.runtime && (
                                            <span className="text-xs text-zinc-400 flex items-center gap-1">
                                                <Clock className="h-3 w-3" /> {detail.runtime} min
                                            </span>
                                        )}
                                    </div>
                                    <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight drop-shadow-md">
                                        {detail.title}
                                    </h2>
                                </div>

                                {detail.trailer_key && (
                                    <Button
                                        size="sm"
                                        onClick={() => setIsPlayingTrailer(true)}
                                        className="bg-red-600 hover:bg-red-500 text-white gap-1.5 shadow-lg shrink-0 rounded-full px-4"
                                    >
                                        <Play className="h-4 w-4 fill-white" /> Bande-annonce
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Trailer Video Player Overlay */}
                        {isPlayingTrailer && detail.trailer_key && (
                            <div className="p-4 bg-black border-b border-zinc-800 relative">
                                <div className="aspect-video w-full rounded-lg overflow-hidden shadow-2xl">
                                    <iframe
                                        src={`https://www.youtube.com/embed/${detail.trailer_key}?autoplay=1`}
                                        title={`${detail.title} Trailer`}
                                        className="w-full h-full border-0"
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                    />
                                </div>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setIsPlayingTrailer(false)}
                                    className="mt-2 text-xs text-zinc-400 hover:text-white"
                                >
                                    Fermer la vidéo
                                </Button>
                            </div>
                        )}

                        {/* Main Content Info */}
                        <div className="p-6 space-y-6">
                            <div className="grid grid-cols-1 md:grid-cols-[180px_1fr] gap-6">
                                {/* Poster */}
                                <div className="hidden md:block shrink-0">
                                    <div className="w-[180px] aspect-[2/3] rounded-xl overflow-hidden border border-zinc-800 shadow-xl">
                                        {detail.poster_url ? (
                                            <img
                                                src={detail.poster_url}
                                                alt={detail.title}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full bg-zinc-800 flex items-center justify-center">
                                                {detail.type === "movie" ? (
                                                    <Film className="h-12 w-12 text-zinc-600" />
                                                ) : (
                                                    <Tv className="h-12 w-12 text-zinc-600" />
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Metas & Details */}
                                <div className="space-y-4">
                                    {/* Action Bar */}
                                    <div className="flex flex-wrap items-center gap-3">
                                        {detail.in_library && detail.library_item ? (
                                            <Link href={`/media/${detail.library_item.type}/${detail.library_item.id}`}>
                                                <Button className="bg-emerald-600 hover:bg-emerald-500 text-white gap-2 shadow-lg">
                                                    <Check className="h-4 w-4" /> Dans votre médiathèque
                                                    <ExternalLink className="h-3.5 w-3.5 opacity-70" />
                                                </Button>
                                            </Link>
                                        ) : (
                                            <Button
                                                onClick={handleAddRequest}
                                                disabled={createRequest.isPending}
                                                className="bg-primary hover:bg-primary/90 text-primary-foreground gap-2 shadow-lg shadow-primary/20 font-semibold"
                                            >
                                                {createRequest.isPending ? (
                                                    <Loader2 className="h-4 w-4 animate-spin" />
                                                ) : (
                                                    <Plus className="h-4 w-4" />
                                                )}
                                                Ajouter à la médiathèque
                                            </Button>
                                        )}

                                        {detail.rating != null && detail.rating > 0 && (
                                            <Badge variant="outline" className="px-3 py-1 bg-yellow-500/10 text-yellow-300 border-yellow-500/30 gap-1 text-xs">
                                                <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                                                <span>{detail.rating.toFixed(1)} / 10</span>
                                                <span className="text-[10px] text-zinc-400">({detail.vote_count} votes)</span>
                                            </Badge>
                                        )}
                                    </div>

                                    {/* Genres */}
                                    {detail.genres && detail.genres.length > 0 && (
                                        <div className="flex flex-wrap gap-1.5">
                                            {detail.genres.map((g) => (
                                                <Badge key={g} variant="secondary" className="bg-zinc-800 text-zinc-300 text-xs">
                                                    {g}
                                                </Badge>
                                            ))}
                                        </div>
                                    )}

                                    {/* Director / Creator */}
                                    {detail.director && (
                                        <p className="text-xs text-zinc-400">
                                            <span className="text-zinc-200 font-semibold">Réalisation / Création : </span>
                                            {detail.director}
                                        </p>
                                    )}

                                    {/* Overview */}
                                    <div className="space-y-1.5">
                                        <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400">Synopsis</h4>
                                        <p className="text-sm text-zinc-300 leading-relaxed font-normal">
                                            {detail.overview}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* Cast Row */}
                            {detail.cast && detail.cast.length > 0 && (
                                <div className="space-y-3 pt-4 border-t border-zinc-800/80">
                                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-400 flex items-center gap-1.5">
                                        <User className="h-3.5 w-3.5 text-indigo-400" /> Acteurs principaux
                                    </h4>
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                        {detail.cast.map((actor, i) => (
                                            <div key={i} className="flex items-center gap-2.5 bg-zinc-900/60 p-2 rounded-lg border border-zinc-800/60">
                                                <div className="h-10 w-10 rounded-full overflow-hidden shrink-0 bg-zinc-800 border border-zinc-700/50">
                                                    {actor.profile_path ? (
                                                        <img src={actor.profile_path} alt={actor.name} className="h-full w-full object-cover" />
                                                    ) : (
                                                        <div className="h-full w-full flex items-center justify-center text-zinc-500">
                                                            <User className="h-5 w-5" />
                                                        </div>
                                                    )}
                                                </div>
                                                <div className="min-w-0">
                                                    <p className="text-xs font-semibold text-white truncate">{actor.name}</p>
                                                    <p className="text-[10px] text-zinc-400 truncate">{actor.character}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ) : null}
            </DialogContent>
        </Dialog>
    );
}
