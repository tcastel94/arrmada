"use client";

/**
 * Formulaire « quelle version veux-tu ? » : langue, doublage, qualité.
 * ----------------------------------------------------------------
 * Composant purement visuel (aucun appel réseau) : il reçoit une valeur et
 * prévient quand elle change. Réutilisé par la fiche d'un titre et par
 * l'action groupée de la médiathèque.
 *
 * `choices` = versions que le serveur sait fournir. Une version absente est
 * grisée (données TRaSH incomplètes) ; sans `choices`, tout est proposé.
 */
import { Check } from "lucide-react";
import type { VersionChoice, VersionDub, VersionLanguage, VersionQuality } from "@/hooks/use-media-version";
import { cn } from "@/lib/utils";
import { DUB_OPTIONS, LANGUAGE_OPTIONS, QUALITY_OPTIONS } from "./version-options";

export interface PickerValue {
    language: VersionLanguage | null;
    /** null = « inchangée » (action groupée uniquement). */
    quality: VersionQuality | null;
    dub: VersionDub;
}

/** Petit groupe de boutons exclusifs (radio), sans dépendance d'animation. */
function Choices<T extends string>({
    label,
    value,
    options,
    onChange,
}: {
    label: string;
    value: T;
    options: { value: T; label: string; disabled?: boolean; title?: string }[];
    onChange: (v: T) => void;
}) {
    return (
        <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-1.5">
            {options.map((o) => (
                <button
                    key={o.value}
                    type="button"
                    role="radio"
                    aria-checked={o.value === value}
                    data-active={o.value === value}
                    disabled={o.disabled}
                    title={o.title}
                    onClick={() => onChange(o.value)}
                    className="chip disabled:cursor-not-allowed disabled:opacity-40"
                >
                    {o.label}
                </button>
            ))}
        </div>
    );
}

export function VersionPicker({
    value,
    onChange,
    choices,
    allowKeepQuality = false,
}: {
    value: PickerValue;
    onChange: (v: PickerValue) => void;
    choices?: VersionChoice[];
    /** Propose « Inchangée » pour la qualité (action groupée). */
    allowKeepQuality?: boolean;
}) {
    const has = (language: VersionLanguage, quality?: VersionQuality | null, dub: VersionDub = "any") =>
        !choices || choices.some((c) => c.language === language && c.dub === dub && (!quality || c.quality === quality));

    const pickLanguage = (language: VersionLanguage) => {
        // Qualité gardée si elle existe pour cette langue, sinon la première disponible.
        let quality = value.quality;
        if (quality && !has(language, quality)) {
            quality = QUALITY_OPTIONS.find((q) => has(language, q.value))?.value ?? quality;
        }
        onChange({ language, quality, dub: language === "vf" ? value.dub : "any" });
    };

    return (
        <div className="space-y-5">
            {/* ── Langue ── */}
            <fieldset className="space-y-2">
                <legend className="text-sm font-medium leading-none">Version audio</legend>
                <div role="radiogroup" aria-label="Version audio" className="grid gap-2 pt-1 sm:grid-cols-2">
                    {LANGUAGE_OPTIONS.map((o) => {
                        const active = value.language === o.value;
                        const available = has(o.value);
                        const Icon = o.icon;
                        return (
                            <button
                                key={o.value}
                                type="button"
                                role="radio"
                                aria-checked={active}
                                disabled={!available}
                                onClick={() => pickLanguage(o.value)}
                                className={cn(
                                    "relative flex items-start gap-3 rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
                                    active ? "border-primary/60 bg-primary/[0.1]" : "border-white/[0.06] bg-background/40 hover:bg-white/[0.04]",
                                    !available && "cursor-not-allowed opacity-40 hover:bg-background/40",
                                )}
                            >
                                <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")} aria-hidden />
                                <span className="min-w-0 flex-1">
                                    <span className="block text-sm font-semibold">{o.label}</span>
                                    <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">
                                        {available ? o.desc : "Indisponible : resynchronise les données TRaSH."}
                                    </span>
                                </span>
                                {active && <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden />}
                            </button>
                        );
                    })}
                </div>
            </fieldset>

            {/* ── Doublage (VF seulement) ── */}
            {value.language === "vf" && (
                <fieldset className="space-y-2">
                    <legend className="text-sm font-medium leading-none">Doublage préféré</legend>
                    <div className="pt-1">
                        <Choices
                            label="Doublage préféré"
                            value={value.dub}
                            onChange={(dub) => onChange({ ...value, dub })}
                            options={DUB_OPTIONS.map((o) => ({
                                value: o.value,
                                label: o.label,
                                disabled: !has("vf", value.quality, o.value),
                            }))}
                        />
                    </div>
                    <p className="text-xs leading-snug text-muted-foreground">
                        {value.dub === "any"
                            ? "N'importe quel doublage français est accepté."
                            : `Une préférence, pas un blocage : faute de mieux, l'autre doublage est pris, puis remplacé dès qu'une release ${
                                  value.dub === "france" ? "VFF" : "VFQ"
                              } sort.`}
                    </p>
                </fieldset>
            )}

            {/* ── Qualité ── */}
            <fieldset className="space-y-2">
                <legend className="text-sm font-medium leading-none">Qualité visée</legend>
                <div className="pt-1">
                    <Choices
                        label="Qualité visée"
                        value={value.quality ?? "keep"}
                        onChange={(q) => onChange({ ...value, quality: q === "keep" ? null : q })}
                        options={[
                            ...(allowKeepQuality ? [{ value: "keep" as const, label: "Inchangée", title: "Chaque titre garde sa qualité actuelle" }] : []),
                            ...QUALITY_OPTIONS.map((o) => ({
                                value: o.value,
                                label: o.label,
                                title: o.desc,
                                disabled: !!value.language && !has(value.language, o.value),
                            })),
                        ]}
                    />
                </div>
            </fieldset>
        </div>
    );
}
