"use client";

/**
 * Tuile de chiffre clé, façon widget iOS : libellé gris en haut, grand
 * chiffre, ligne de détail, et en option un anneau de progression.
 * Cliquable si `href` est fourni.
 */
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { RingGauge, type GaugeTone } from "@/components/fx/ring-gauge";
import { cn } from "@/lib/utils";

export function StatTile({
    label,
    value,
    detail,
    icon: Icon,
    iconClassName = "text-muted-foreground",
    gauge,
    tone = "primary",
    href,
    className,
}: {
    label: string;
    value: ReactNode;
    detail?: ReactNode;
    icon?: LucideIcon;
    iconClassName?: string;
    /** 0-100 : anneau à droite. */
    gauge?: number;
    tone?: GaugeTone;
    href?: string;
    className?: string;
}) {
    const body = (
        <div className="flex h-full items-center gap-3">
            <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground">
                    {Icon && <Icon className={cn("h-3.5 w-3.5", iconClassName)} strokeWidth={2.2} />}
                    {label}
                </p>
                <p className="mt-1 truncate text-[26px] font-bold leading-none tracking-tight tabular-nums">{value}</p>
                {detail && <p className="mt-1.5 truncate text-[12px] text-muted-foreground">{detail}</p>}
            </div>
            {typeof gauge === "number" && (
                <RingGauge value={gauge} size={46} stroke={5} tone={tone}>
                    <span className="text-[10px] font-semibold tabular-nums text-muted-foreground">{Math.round(gauge)}%</span>
                </RingGauge>
            )}
        </div>
    );
    const cls = cn("block rounded-2xl bg-card p-4", href && "pressable hover:bg-[hsl(240_3%_13%)]", className);
    return href ? (
        <Link href={href} className={cls}>
            {body}
        </Link>
    ) : (
        <div className={cls}>{body}</div>
    );
}
