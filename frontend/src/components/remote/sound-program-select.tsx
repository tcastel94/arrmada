"use client";

/**
 * Liste déroulante des programmes sonores Yamaha, regroupés par usage
 * (Cinéma / TV & jeux / Musique). Si la valeur actuelle n'est pas dans
 * la liste (programme propre à un modèle, ou identifiant historique),
 * elle reste affichée en tête au lieu de disparaître silencieusement.
 */
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { KNOWN_PROGRAM_IDS, SOUND_PROGRAM_GROUPS, soundProgramLabel } from "./yamaha-audio";

interface SoundProgramSelectProps {
    value?: string | null;
    onChange: (program: string) => void;
    /** Pour relier un <Label htmlFor> visible. */
    id?: string;
    ariaLabel?: string;
    size?: "sm" | "md";
    disabled?: boolean;
    className?: string;
}

export function SoundProgramSelect({ value, onChange, id, ariaLabel, size = "md", disabled, className }: SoundProgramSelectProps) {
    const extra = value && !KNOWN_PROGRAM_IDS.has(value) ? value : null;
    return (
        <Select value={value ?? undefined} onValueChange={onChange} disabled={disabled}>
            <SelectTrigger id={id} aria-label={ariaLabel} className={cn(size === "sm" && "h-8 text-xs", className)}>
                <SelectValue placeholder="Choisir un programme" />
            </SelectTrigger>
            <SelectContent className="max-h-80">
                {extra && (
                    <SelectGroup>
                        <SelectLabel className="eyebrow">Valeur actuelle</SelectLabel>
                        <SelectItem value={extra}>{soundProgramLabel(extra)}</SelectItem>
                    </SelectGroup>
                )}
                {SOUND_PROGRAM_GROUPS.map((g) => (
                    <SelectGroup key={g.label}>
                        <SelectLabel className="eyebrow pt-2.5">{g.label}</SelectLabel>
                        {g.items.map((p) => (
                            <SelectItem key={p.id} value={p.id}>
                                {p.label}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                ))}
            </SelectContent>
        </Select>
    );
}
