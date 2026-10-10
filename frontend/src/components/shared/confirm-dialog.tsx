"use client";

/**
 * Boîte de confirmation standard (remplace window.confirm).
 * ----------------------------------------------------------------
 * Usage contrôlé :
 *   <ConfirmDialog open={open} onOpenChange={setOpen}
 *       title="Supprimer ?" description="…" destructive
 *       confirmLabel="Supprimer" onConfirm={async () => { … }} />
 * Si onConfirm renvoie une Promise, le bouton affiche un spinner et la
 * boîte reste ouverte tant que l'action n'est pas terminée.
 */
import { useState, type ReactNode } from "react";
import { AlertTriangle, Loader2, ShieldQuestion } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ConfirmDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description?: ReactNode;
    /** Contenu additionnel (options, cases à cocher…). */
    children?: ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
    destructive?: boolean;
    onConfirm: () => void | Promise<unknown>;
    /** Force l'état « en cours » depuis l'extérieur. */
    loading?: boolean;
}

export function ConfirmDialog({
    open,
    onOpenChange,
    title,
    description,
    children,
    confirmLabel = "Confirmer",
    cancelLabel = "Annuler",
    destructive = false,
    onConfirm,
    loading,
}: ConfirmDialogProps) {
    const [running, setRunning] = useState(false);
    const busy = loading ?? running;

    const handleConfirm = async () => {
        try {
            setRunning(true);
            await onConfirm();
            onOpenChange(false);
        } catch {
            // L'appelant affiche son propre toast d'erreur ; on garde la boîte ouverte.
        } finally {
            setRunning(false);
        }
    };

    const Icon = destructive ? AlertTriangle : ShieldQuestion;

    return (
        <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <div className="flex items-start gap-4">
                        <div
                            className={cn(
                                "flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ring-1",
                                destructive
                                    ? "bg-red-500/15 text-red-400 ring-red-500/30 shadow-[0_0_24px_-6px] shadow-red-500/50"
                                    : "bg-primary/15 text-primary ring-primary/30 shadow-[0_0_24px_-6px] shadow-primary/50",
                            )}
                        >
                            <Icon className="h-5 w-5" />
                        </div>
                        <div className="space-y-1.5 pt-0.5 text-left">
                            <DialogTitle>{title}</DialogTitle>
                            {description && <DialogDescription>{description}</DialogDescription>}
                        </div>
                    </div>
                </DialogHeader>
                {children && <div className="space-y-3">{children}</div>}
                <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={busy}>
                        {cancelLabel}
                    </Button>
                    <Button variant={destructive ? "destructive" : "default"} onClick={handleConfirm} disabled={busy}>
                        {busy && <Loader2 className="h-4 w-4 animate-spin" />}
                        {confirmLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
