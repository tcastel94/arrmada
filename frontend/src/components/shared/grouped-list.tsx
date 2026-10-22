"use client";

/**
 * Listes groupées iOS (comme l'app Réglages).
 * ----------------------------------------------------------------
 *   <GroupedList title="Lecture" footer="Explication en gris sous la carte">
 *     <ListRow icon={Tv} tint="bg-[#0A84FF]" title="Shield Salon" detail="En ligne" href="/…" />
 *     <ListRow title="Sous-titres" accessory={<Switch …/>} />
 *   </GroupedList>
 * Chaque ligne : vignette colorée optionnelle, titre (+ sous-titre),
 * valeur grise à droite, accessoire (interrupteur, badge…) et chevron
 * si la ligne mène quelque part. Les filets entre lignes commencent après
 * la vignette, exactement comme sur iPhone.
 */
import Link from "next/link";
import { ChevronRight, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function GroupedList({
    title,
    footer,
    children,
    className,
}: {
    title?: ReactNode;
    footer?: ReactNode;
    children: ReactNode;
    className?: string;
}) {
    return (
        <section className={cn("min-w-0", className)}>
            {title && <h2 className="mb-1.5 px-4 text-[13px] uppercase text-muted-foreground">{title}</h2>}
            <div className="overflow-hidden rounded-xl bg-card [&>*+*]:shadow-[inset_0_0.5px_0_hsl(0_0%_100%/0.1)]">{children}</div>
            {footer && <p className="mt-1.5 px-4 text-[13px] leading-snug text-muted-foreground">{footer}</p>}
        </section>
    );
}

export function ListRow({
    icon: Icon,
    tint,
    leading,
    title,
    subtitle,
    detail,
    accessory,
    href,
    onClick,
    destructive,
    chevron,
    className,
}: {
    icon?: LucideIcon;
    /** Couleur de la vignette d'icône (ex : "bg-[#30D158]"). Sans tint : icône grise sans fond. */
    tint?: string;
    /** Élément libre à gauche (affiche, avatar…), remplace l'icône. */
    leading?: ReactNode;
    title: ReactNode;
    subtitle?: ReactNode;
    /** Valeur grise à droite (ex : « En ligne », « 42 % »). */
    detail?: ReactNode;
    /** Contrôle à droite (interrupteur, bouton, badge). */
    accessory?: ReactNode;
    href?: string;
    onClick?: () => void;
    destructive?: boolean;
    /** Force / masque le chevron (par défaut : visible si la ligne est un lien). */
    chevron?: boolean;
    className?: string;
}) {
    const showChevron = chevron ?? !!href;
    const content = (
        <>
            {leading ??
                (Icon &&
                    (tint ? (
                        <span className={cn("flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[8px] text-white", tint)}>
                            <Icon className="h-[18px] w-[18px]" strokeWidth={2.1} />
                        </span>
                    ) : (
                        <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
                    )))}
            <span className="min-w-0 flex-1 py-2.5">
                <span className={cn("block truncate text-[16px] leading-snug", destructive && "text-destructive")}>{title}</span>
                {subtitle && <span className="block truncate text-[13px] leading-snug text-muted-foreground">{subtitle}</span>}
            </span>
            {detail != null && detail !== "" && <span className="max-w-[45%] shrink-0 truncate text-[15px] text-muted-foreground">{detail}</span>}
            {accessory && <span className="flex shrink-0 items-center">{accessory}</span>}
            {showChevron && <ChevronRight className="h-[18px] w-[18px] shrink-0 text-white/25" strokeWidth={2.5} />}
        </>
    );
    const base = cn("flex min-h-[46px] w-full items-center gap-3 pl-4 pr-3 text-left", className);
    if (href)
        return (
            <Link href={href} className={cn(base, "transition-colors hover:bg-white/[0.03] active:bg-white/[0.06]")}>
                {content}
            </Link>
        );
    if (onClick)
        return (
            <button type="button" onClick={onClick} className={cn(base, "transition-colors hover:bg-white/[0.03] active:bg-white/[0.06]")}>
                {content}
            </button>
        );
    return <div className={base}>{content}</div>;
}
