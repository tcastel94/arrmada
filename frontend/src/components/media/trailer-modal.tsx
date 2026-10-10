"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Play, Tv, X } from "lucide-react";
import { cn } from "@/lib/utils";

export interface TrailerModalProps {
    youtubeId?: string | null;
    title: string;
    className?: string;
}

export function TrailerModal({ youtubeId, title, className }: TrailerModalProps) {
    const [open, setOpen] = useState(false);

    if (!youtubeId) return null;

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button
                    variant="default"
                    size="sm"
                    className={cn("bg-red-600/90 hover:bg-red-600 text-white font-medium shadow-md shadow-red-950/20", className)}
                >
                    <Play className="h-4 w-4 mr-2 fill-white" />
                    Bande-annonce
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-4xl p-0 overflow-hidden bg-black/95 border-red-900/30">
                <DialogHeader className="p-4 bg-zinc-900/80 flex flex-row items-center justify-between border-b border-zinc-800">
                    <DialogTitle className="text-base font-semibold flex items-center gap-2 text-white">
                        <Tv className="h-4 w-4 text-red-500" />
                        Bande-annonce — {title}
                    </DialogTitle>
                </DialogHeader>
                <div className="relative aspect-video w-full bg-black flex items-center justify-center">
                    {open && (
                        <iframe
                            src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&rel=0`}
                            title={`Bande-annonce ${title}`}
                            className="w-full h-full border-0"
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                        />
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
