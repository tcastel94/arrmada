"use client";

/**
 * Éditeur des profils audio par pièce (Paramètres → Ampli Yamaha).
 * ----------------------------------------------------------------
 * Deux profils, « Salon » et « Salle de cinéma », appliqués d'un clic
 * depuis le Salon (/remote, boutons « Préréglage ») : volume de départ,
 * programmes sonores selon le média (films / séries / musique), voix,
 * traitements (mode nuit, enhancer, extra bass) et source.
 * Enregistrés côté backend dans data/yamaha_room_profiles.json.
 *
 * Principe du formulaire : on ne stocke QUE les champs modifiés
 * (« brouillon ») par-dessus le profil enregistré. Avantages : savoir
 * exactement ce qui a changé (bouton Enregistrer actif, pastille « non
 * enregistré »), et une relecture du profil en arrière-plan n'écrase
 * jamais une saisie en cours.
 */
import { useState, type FormEvent, type ReactNode } from "react";
import { motion } from "framer-motion";
import { AudioLines, Loader2, Play, RotateCcw, Save } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RangeSlider } from "@/components/remote/range-slider";
import { StepPicker } from "@/components/remote/step-picker";
import { SoundProgramSelect } from "@/components/remote/sound-program-select";
import {
    PRESET_VOLUME_CAP,
    ROOMS,
    ROOM_META,
    YAMAHA_MAX_VOLUME,
    describeApplied,
    soundProgramShortLabel,
    volumeDb,
    volumePct,
} from "@/components/remote/yamaha-audio";
import { inputLabel } from "@/components/yamaha-remote";
import {
    useApplyYamahaPreset,
    useSaveYamahaProfile,
    useYamahaInputs,
    useYamahaProfiles,
    type RoomProfile,
    type YamahaRoom,
} from "@/hooks/use-yamaha";
import { SPRING } from "@/lib/motion";
import { cn } from "@/lib/utils";

/** Champs modifiables (le nom de la pièce reste fixe). */
type EditableProfile = Omit<RoomProfile, "name" | "volume_pct">;
type Draft = Partial<EditableProfile>;

/** Valeur sentinelle « ne pas changer de source » (Radix refuse ""). */
const KEEP_INPUT = "__keep__";

export function RoomProfilesPanel({ hasAmp }: { hasAmp: boolean }) {
    const { data: profiles, isLoading, isError, error, refetch } = useYamahaProfiles();
    const [room, setRoom] = useState<YamahaRoom>("salon");
    // Pièces avec des modifications non enregistrées (pastille sur l'onglet).
    const [dirtyRooms, setDirtyRooms] = useState<Record<YamahaRoom, boolean>>({ salon: false, cinema: false });

    return (
        <Panel title="Profils audio par pièce" icon={AudioLines} iconClassName="text-primary" bodyClassName="space-y-5">
            <p className="text-xs leading-relaxed text-muted-foreground">
                Appliqués d&apos;un clic depuis le Salon (« Préréglages »). Si Kodi lit quelque chose, le programme sonore suit le
                type de média : film, série ou musique.
            </p>

            {isLoading ? (
                <div className="space-y-4">
                    <div className="grid grid-cols-2 gap-2">
                        <Shimmer className="h-16" />
                        <Shimmer className="h-16" />
                    </div>
                    <Shimmer className="h-40" />
                    <Shimmer className="h-24" />
                </div>
            ) : isError || !profiles ? (
                <ErrorState compact error={error} onRetry={() => refetch()} title="Profils illisibles" />
            ) : (
                <>
                    {/* Choix de la pièce : tuiles façon onglets, avec résumé du profil */}
                    <div role="tablist" aria-label="Pièce à configurer" className="grid grid-cols-2 gap-2">
                        {ROOMS.map((r) => {
                            const meta = ROOM_META[r];
                            const Icon = meta.icon;
                            const p = profiles[r];
                            const active = r === room;
                            return (
                                <button
                                    key={r}
                                    type="button"
                                    role="tab"
                                    id={`room-tab-${r}`}
                                    aria-selected={active}
                                    aria-controls={`room-panel-${r}`}
                                    onClick={() => setRoom(r)}
                                    className={cn(
                                        "relative flex min-w-0 items-center gap-2.5 rounded-xl p-2.5 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 sm:gap-3 sm:p-3",
                                        active ? "text-foreground" : "glass glass-hover text-muted-foreground",
                                    )}
                                >
                                    {active && (
                                        <motion.span
                                            layoutId="room-profile-tab"
                                            transition={SPRING}
                                            className="absolute inset-0 rounded-xl border border-primary/35 bg-primary/[0.08]"
                                        />
                                    )}
                                    <span className={cn("relative flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ring-1 sm:h-10 sm:w-10", meta.tile)}>
                                        <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
                                    </span>
                                    <span className="relative min-w-0">
                                        <span className="flex items-center gap-1.5 text-sm font-semibold">
                                            {/* Libellé court sur mobile (deux tuiles côte à côte) */}
                                            <span className="truncate sm:hidden">{meta.short}</span>
                                            <span className="hidden truncate sm:inline">{meta.label}</span>
                                            {dirtyRooms[r] && (
                                                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-warning" title="Modifications non enregistrées">
                                                    <span className="sr-only">(non enregistré)</span>
                                                </span>
                                            )}
                                        </span>
                                        <span className="block truncate text-[11px] text-muted-foreground">
                                            {volumePct(p.volume_raw)} % · {soundProgramShortLabel(p.movie_sound_program)}
                                        </span>
                                    </span>
                                </button>
                            );
                        })}
                    </div>

                    {/* Les deux éditeurs restent montés : changer d'onglet ne perd pas la saisie. */}
                    {ROOMS.map((r) => (
                        <div key={r} role="tabpanel" id={`room-panel-${r}`} aria-labelledby={`room-tab-${r}`} hidden={r !== room}>
                            <ProfileEditor
                                room={r}
                                saved={profiles[r]}
                                hasAmp={hasAmp}
                                onDirtyChange={(dirty) => setDirtyRooms((d) => (d[r] === dirty ? d : { ...d, [r]: dirty }))}
                            />
                        </div>
                    ))}
                </>
            )}
        </Panel>
    );
}

/* ── Éditeur d'un profil ────────────────────────────────────── */

function ProfileEditor({
    room,
    saved,
    hasAmp,
    onDirtyChange,
}: {
    room: YamahaRoom;
    saved: RoomProfile;
    hasAmp: boolean;
    onDirtyChange: (dirty: boolean) => void;
}) {
    const save = useSaveYamahaProfile();
    const apply = useApplyYamahaPreset();
    const { data: inputs } = useYamahaInputs(undefined, hasAmp);
    const [draft, setDraftState] = useState<Draft>({});
    const label = ROOM_META[room].label;
    const idp = `profile-${room}`;

    const values: EditableProfile = { ...saved, ...draft };
    const dirty = Object.keys(draft).length > 0;

    const setDraft = (next: Draft) => {
        setDraftState(next);
        onDirtyChange(Object.keys(next).length > 0);
    };

    /** Modifie un champ ; revenir à la valeur enregistrée le retire du brouillon. */
    const set = <K extends keyof EditableProfile>(key: K, value: EditableProfile[K]) => {
        const next: Draft = { ...draft, [key]: value };
        if (saved[key] === value || (saved[key] == null && value == null)) delete next[key];
        setDraft(next);
    };

    /** Envoie le brouillon ; le pourcentage suit toujours le volume brut. */
    const persist = async () => {
        const payload: Partial<RoomProfile> = { ...draft };
        if (draft.volume_raw !== undefined) payload.volume_pct = volumePct(draft.volume_raw);
        await save.mutateAsync({ room, profile: payload });
        setDraft({});
    };

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        if (!dirty) return;
        try {
            await persist();
            toast.success(`Profil ${label} enregistré`);
        } catch (err) {
            toast.error("Enregistrement impossible", { description: err instanceof Error ? err.message : undefined });
        }
    };

    /** Essai en direct : enregistre d'abord si besoin, puis applique sur l'ampli. */
    const handleApply = async () => {
        try {
            if (dirty) await persist();
            const res = await apply.mutateAsync({ room });
            toast.success(dirty ? `Profil ${label} enregistré et appliqué` : `Préréglage ${label} appliqué`, {
                description: describeApplied(res.applied, inputLabel),
            });
        } catch (err) {
            toast.error(`Préréglage ${label} : échec`, { description: err instanceof Error ? err.message : undefined });
        }
    };

    const busy = save.isPending || apply.isPending;
    const pct = volumePct(values.volume_raw);
    const inputOptions = Array.from(new Set([...(inputs ?? []), values.input].filter((i): i is string => !!i)));

    return (
        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Volume */}
            <Section title="Volume de départ">
                <div className="flex items-baseline justify-between gap-3">
                    <span id={`${idp}-vol`} className="text-xs text-muted-foreground">
                        Appliqué à l&apos;activation du préréglage
                    </span>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">
                        {pct} % <span className="text-xs font-normal text-muted-foreground">· {volumeDb(values.volume_raw)}</span>
                    </span>
                </div>
                <RangeSlider
                    value={Math.min(values.volume_raw, PRESET_VOLUME_CAP)}
                    max={PRESET_VOLUME_CAP}
                    onChange={(v) => set("volume_raw", v)}
                    tone="orange"
                    ariaLabel={`Volume de départ du profil ${label}`}
                    ariaValueText={`${pct} %, ${volumeDb(values.volume_raw)}`}
                    bubble={(v) => `${volumePct(v)} %`}
                />
                <p className="text-[11px] text-muted-foreground">
                    Plafonné à {volumePct(PRESET_VOLUME_CAP)} % ({PRESET_VOLUME_CAP}/{YAMAHA_MAX_VOLUME}) par sécurité : protège tes enceintes
                    d&apos;un préréglage trop fort.
                </p>
            </Section>

            {/* Programmes sonores */}
            <Section title="Programmes sonores" hint="Choisi selon ce que Kodi lit au moment d'appliquer le préréglage.">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {(
                        [
                            ["movie_sound_program", "Films"],
                            ["series_sound_program", "Séries"],
                            ["music_sound_program", "Musique"],
                        ] as const
                    ).map(([key, text]) => (
                        <div key={key} className="min-w-0 space-y-1.5">
                            <Label htmlFor={`${idp}-${key}`} className="text-xs">
                                {text}
                            </Label>
                            <SoundProgramSelect id={`${idp}-${key}`} value={values[key]} onChange={(v) => set(key, v)} />
                        </div>
                    ))}
                </div>
            </Section>

            {/* Voix */}
            <Section title="Voix">
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="min-w-0 space-y-1.5">
                        <p id={`${idp}-lift`} className="text-xs font-medium">
                            Rehaussement des voix
                        </p>
                        <StepPicker
                            layoutId={`${idp}-lift-pill`}
                            ariaLabelledBy={`${idp}-lift`}
                            ariaDescribedBy={`${idp}-lift-hint`}
                            value={values.dialog_lift}
                            max={5}
                            onChange={(v) => set("dialog_lift", v)}
                        />
                        <p id={`${idp}-lift-hint`} className="text-[11px] leading-relaxed text-muted-foreground">
                            Remonte virtuellement les voix vers l&apos;écran.
                        </p>
                    </div>
                    <div className="min-w-0 space-y-1.5">
                        <p id={`${idp}-level`} className="text-xs font-medium">
                            Niveau des dialogues
                        </p>
                        <StepPicker
                            layoutId={`${idp}-level-pill`}
                            ariaLabelledBy={`${idp}-level`}
                            ariaDescribedBy={`${idp}-level-hint`}
                            value={values.dialog_level}
                            max={3}
                            onChange={(v) => set("dialog_level", v)}
                        />
                        <p id={`${idp}-level-hint`} className="text-[11px] leading-relaxed text-muted-foreground">
                            Rend les dialogues plus intelligibles face aux effets.
                        </p>
                    </div>
                </div>
            </Section>

            {/* Traitements */}
            <Section title="Traitements">
                <div className="divide-y divide-white/[0.05] rounded-xl border border-white/[0.06] bg-white/[0.02]">
                    <ToggleRow
                        id={`${idp}-drc`}
                        label="Mode nuit (DRC adaptatif)"
                        hint="Réduit l'écart entre explosions et dialogues : idéal à bas volume."
                        checked={values.adaptive_drc}
                        onChange={(v) => set("adaptive_drc", v)}
                    />
                    <ToggleRow
                        id={`${idp}-enhancer`}
                        label="Enhancer"
                        hint="Restaure les aigus des sources compressées (streaming, MP3)."
                        checked={values.enhancer}
                        onChange={(v) => set("enhancer", v)}
                    />
                    <ToggleRow
                        id={`${idp}-bass`}
                        label="Extra Bass"
                        hint="Renforce le grave, utile sans caisson ou avec de petites enceintes."
                        checked={values.extra_bass}
                        onChange={(v) => set("extra_bass", v)}
                    />
                </div>
            </Section>

            {/* Source */}
            <Section title="Source">
                <div className="space-y-1.5 sm:max-w-xs">
                    <Label htmlFor={`${idp}-input`} className="text-xs">
                        Entrée à sélectionner
                    </Label>
                    <Select value={values.input ?? KEEP_INPUT} onValueChange={(v) => set("input", v === KEEP_INPUT ? null : v)}>
                        <SelectTrigger id={`${idp}-input`}>
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="max-h-72">
                            <SelectItem value={KEEP_INPUT}>Ne pas changer</SelectItem>
                            {inputOptions.map((i) => (
                                <SelectItem key={i} value={i}>
                                    {inputLabel(i)}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <p className="text-[11px] text-muted-foreground">
                        {hasAmp ? "Ex : l'entrée HDMI de ton lecteur Kodi." : "La liste des entrées s'affichera une fois l'ampli ajouté."}
                    </p>
                </div>
            </Section>

            {/* Actions */}
            <div className="flex flex-col-reverse gap-2 border-t border-white/[0.05] pt-4 sm:flex-row sm:items-center sm:justify-end">
                {dirty && (
                    <Button type="button" variant="ghost" onClick={() => setDraft({})} disabled={busy}>
                        <RotateCcw />
                        Annuler les modifications
                    </Button>
                )}
                <Button
                    type="button"
                    variant="outline"
                    onClick={handleApply}
                    disabled={busy || !hasAmp}
                    title={hasAmp ? "Applique ce profil sur l'ampli pour l'écouter" : "Ajoute d'abord un ampli"}
                >
                    {apply.isPending ? <Loader2 className="animate-spin" /> : <Play />}
                    {dirty ? "Enregistrer et essayer" : "Essayer sur l'ampli"}
                </Button>
                <Button type="submit" disabled={!dirty || busy}>
                    {save.isPending ? <Loader2 className="animate-spin" /> : <Save />}
                    Enregistrer
                </Button>
            </div>
        </form>
    );
}

/* ── Briques de mise en page ────────────────────────────────── */

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
    return (
        <fieldset className="min-w-0 space-y-2.5">
            <legend className="eyebrow mb-2.5">{title}</legend>
            {hint && <p className="-mt-1 text-[11px] text-muted-foreground">{hint}</p>}
            {children}
        </fieldset>
    );
}

/** Ligne interrupteur : libellé + explication cliquables, interrupteur à droite. */
function ToggleRow({
    id,
    label,
    hint,
    checked,
    onChange,
}: {
    id: string;
    label: string;
    hint: string;
    checked: boolean;
    onChange: (value: boolean) => void;
}) {
    return (
        <div className="flex items-center justify-between gap-4 px-3.5 py-3">
            <div className="min-w-0">
                <Label htmlFor={id} className="cursor-pointer text-sm">
                    {label}
                </Label>
                <p id={`${id}-hint`} className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {hint}
                </p>
            </div>
            <Switch id={id} checked={checked} onCheckedChange={onChange} aria-describedby={`${id}-hint`} />
        </div>
    );
}
