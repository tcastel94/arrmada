"use client";

/**
 * Liste déroulante de filtre avec petit libellé au-dessus (panneau Filtres).
 * `highlight` met le cadre en couleur quand le filtre n'est pas « tous » :
 * on voit d'un coup d'œil ce qui est actif.
 */
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";

export interface FilterChoice<T extends string> {
    value: T;
    label: string;
}

export function FilterSelect<T extends string>({
    label,
    value,
    onChange,
    choices,
    disabled,
    hint,
    id,
}: {
    label: string;
    value: T;
    onChange: (value: T) => void;
    choices: FilterChoice<T>[];
    disabled?: boolean;
    /** Petit texte d'aide sous la liste (ex: « Bazarr non configuré »). */
    hint?: string;
    id: string;
}) {
    const active = value !== choices[0]?.value;
    return (
        <div className="min-w-0 space-y-1.5">
            <label htmlFor={id} className="eyebrow block">
                {label}
            </label>
            <Select value={value} onValueChange={(v) => onChange(v as T)} disabled={disabled}>
                <SelectTrigger
                    id={id}
                    className={cn(active && "border-primary/40 bg-primary/[0.07] text-primary shadow-[0_0_18px_-8px_hsl(var(--primary)/0.8)]")}
                >
                    <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-72">
                    {choices.map((c) => (
                        <SelectItem key={c.value} value={c.value}>
                            {c.label}
                        </SelectItem>
                    ))}
                </SelectContent>
            </Select>
            {hint && <p className="text-[10px] text-muted-foreground/70">{hint}</p>}
        </div>
    );
}
