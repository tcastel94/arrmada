/**
 * Ancienne carte « holographique » inclinée en 3D au survol.
 * ----------------------------------------------------------------
 * Refonte « Épuré » : plus d'inclinaison ni de reflet. Il reste un
 * conteneur simple, gardé pour les écrans qui l'importent encore.
 */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface TiltCardProps {
    children: ReactNode;
    className?: string;
    /** Options de l'ancien effet, ignorées. */
    max?: number;
    glare?: boolean;
}

export function TiltCard({ children, className }: TiltCardProps) {
    return <div className={cn("group relative", className)}>{children}</div>;
}
