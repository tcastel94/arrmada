"use client";

/**
 * Compatibilité : ancien hook shadcn `useToast`.
 * ----------------------------------------------------------------
 * BUG corrigé : l'ancienne version stockait les toasts dans un state
 * local que RIEN n'affichait → tous les messages de TRaSH Guides,
 * Paramètres, Requêtes… étaient invisibles. On redirige désormais vers
 * sonner (le seul <Toaster> monté dans l'app).
 * Pour du nouveau code, importer directement `toast` depuis "sonner".
 */
import { toast as sonner } from "sonner";

interface Toast {
    title: string;
    description?: string;
    variant?: "default" | "destructive";
}

function toast({ title, description, variant }: Toast) {
    if (variant === "destructive") sonner.error(title, { description });
    else sonner.success(title, { description });
}

export function useToast() {
    return { toast, dismiss: (id?: string | number) => sonner.dismiss(id) };
}

export { toast, type Toast };
