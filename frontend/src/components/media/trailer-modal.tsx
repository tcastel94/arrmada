"use client";

/**
 * Bande-annonce YouTube dans une modale (au lieu d'ouvrir YouTube dans un
 * nouvel onglet).
 * ----------------------------------------------------------------
 * - Lecteur youtube-nocookie.com : pas de cookie publicitaire tant qu'on ne
 *   lance pas la vidéo.
 * - L'iframe n'existe que modale OUVERTE : la vidéo s'arrête net à la
 *   fermeture, et rien n'est chargé tant qu'on ne clique pas.
 * - Taille bornée par la hauteur d'écran (téléphone en paysage) en plus de
 *   la largeur : la vidéo 16:9 tient toujours sans barre de défilement.
 * - Lien « Ouvrir sur YouTube » en secours (certaines vidéos interdisent
 *   la lecture intégrée).
 */
import { useState, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Video } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface TrailerModalProps {
    youtubeId?: string | null;
    /** Titre du film / de la série (titre de la modale + libellés accessibles). */
    title: string;
    /**
     * Bouton déclencheur personnalisé (rendu via `asChild`). Par défaut :
     * bouton discret « Bande-annonce ».
     */
    trigger?: ReactNode;
    className?: string;
}

/** Un identifiant YouTube valide : 11 caractères [A-Za-z0-9_-] (tolérance 6-20). */
const YT_ID = /^[\w-]{6,20}$/;

export function TrailerModal({ youtubeId, title, trigger, className }: TrailerModalProps) {
    const [open, setOpen] = useState(false);
    const [loaded, setLoaded] = useState(false);

    const id = youtubeId?.trim() ?? "";
    // Valeur inattendue (vide, URL complète…) : pas de bouton plutôt qu'un lecteur cassé.
    if (!YT_ID.test(id)) return null;

    const onOpenChange = (next: boolean) => {
        setOpen(next);
        if (!next) setLoaded(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogTrigger asChild>
                {trigger ?? (
                    <Button size="lg" variant="ghost" className={cn("px-3", className)} aria-label={`Voir la bande-annonce de ${title}`}>
                        {/* Pas le clap : il désigne déjà la « Salle de cinéma » dans le bouton Lire voisin. */}
                        <Video />
                        <span className="hidden sm:inline">Bande-annonce</span>
                    </Button>
                )}
            </DialogTrigger>
            <DialogContent
                className={cn(
                    "gap-0 overflow-hidden p-0",
                    // Largeur max = 56rem, ou moins si l'écran est bas (16:9 + ~4rem d'en-tête).
                    "max-w-[min(56rem,calc((90dvh_-_4rem)*16/9))]",
                )}
            >
                <div className="flex items-center gap-3 border-b border-white/[0.06] px-4 py-3 pr-12">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-brand/10 text-primary ring-1 ring-primary/25">
                        <Video className="h-4 w-4" aria-hidden />
                    </span>
                    <div className="min-w-0 flex-1">
                        <DialogTitle className="truncate text-base">{title}</DialogTitle>
                        <DialogDescription className="text-xs">Bande-annonce</DialogDescription>
                    </div>
                    <Button variant="ghost" size="sm" asChild className="hidden shrink-0 text-muted-foreground sm:inline-flex">
                        <a href={`https://www.youtube.com/watch?v=${id}`} target="_blank" rel="noopener noreferrer">
                            <ExternalLink /> Ouvrir sur YouTube
                        </a>
                    </Button>
                </div>

                <div className="relative aspect-video w-full bg-black">
                    {/* Reflet de chargement tant que le lecteur YouTube n'est pas prêt. */}
                    <AnimatePresence>
                        {!loaded && (
                            <motion.div
                                key="loading"
                                initial={{ opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.4 }}
                                className="shimmer absolute inset-0"
                                aria-hidden
                            />
                        )}
                    </AnimatePresence>
                    {open && (
                        <iframe
                            src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&modestbranding=1&playsinline=1`}
                            title={`Bande-annonce de ${title}`}
                            onLoad={() => setLoaded(true)}
                            className="absolute inset-0 h-full w-full border-0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                            // YouTube refuse la lecture intégrée sans référent (erreur 153).
                            referrerPolicy="strict-origin-when-cross-origin"
                            allowFullScreen
                        />
                    )}
                </div>

                {/* Mobile : le lien de secours passe sous la vidéo. */}
                <a
                    href={`https://www.youtube.com/watch?v=${id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-1.5 py-2.5 text-xs text-muted-foreground transition-colors hover:text-foreground sm:hidden"
                >
                    <ExternalLink className="h-3.5 w-3.5" aria-hidden /> Ouvrir sur YouTube
                </a>
            </DialogContent>
        </Dialog>
    );
}
