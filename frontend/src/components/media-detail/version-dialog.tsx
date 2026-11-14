"use client";

/**
 * « Version audio & qualité » d'un film / d'une série.
 * ----------------------------------------------------------------
 * Trois questions, dans l'ordre :
 *   1. quelle version (VF, MULTi, VOSTFR, VO) + quel doublage + quelle qualité ;
 *   2. que faire du fichier déjà présent (le garder, chercher mieux, le
 *      remplacer tout de suite) ;
 *   3. valider.
 *
 * Pourquoi « chercher » ne suffit pas toujours : Radarr ne remplace un fichier
 * que s'il juge la nouvelle release MEILLEURE. Un Blu-ray en VO n'est pas
 * remplacé par un WEB en VF (qualité inférieure à ses yeux), d'où l'option
 * « Remplacer maintenant », qui supprime d'abord le fichier (films seulement).
 *
 * La page remonte ce composant (prop `key`) à chaque ouverture : le
 * formulaire repart toujours de l'état réel.
 */
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Check, CircleHelp, Languages, Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import type { MediaDetail } from "@/hooks/use-media";
import {
    useMediaVersion,
    useSetMediaVersion,
    type MediaVersionState,
    type VersionAction,
    type VersionFileState,
} from "@/hooks/use-media-version";
import { cn } from "@/lib/utils";
import { VersionPicker, type PickerValue } from "./version-picker";
import { languageName, versionLabel } from "./version-options";

/* ── État du fichier présent ───────────────────────────────── */

/** « Français · Anglais — MULTi VFF » + verdict (correspond / ne correspond pas). */
export function FileVerdict({
    file,
    isMovie,
    className,
    showVerdict = true,
}: {
    file: VersionFileState;
    isMovie: boolean;
    className?: string;
    /** Faux tant qu'aucune version n'est choisie : il n'y a rien à quoi comparer le fichier. */
    showVerdict?: boolean;
}) {
    if (!file.has_file) {
        return <p className={cn("text-xs text-muted-foreground", className)}>{isMovie ? "Pas encore téléchargé." : "Aucun épisode téléchargé."}</p>;
    }
    const langs = file.audio_languages.map(languageName).join(" · ");
    const tone = file.matches === true ? "text-success" : file.matches === false ? "text-warning" : "text-muted-foreground";
    const Icon = file.matches === true ? Check : file.matches === false ? AlertTriangle : CircleHelp;
    const verdict =
        file.matches === true
            ? isMovie
                ? "Correspond à la version voulue"
                : "Tous les épisodes correspondent"
            : file.matches === false
              ? isMovie
                  ? `Ne correspond pas${file.reason ? ` : ${file.reason.toLowerCase()}` : ""}`
                  : `${file.files_mismatching} épisode${file.files_mismatching > 1 ? "s" : ""} sur ${file.files_total} ne ${
                        file.files_mismatching > 1 ? "correspondent" : "correspond"
                    } pas`
              : "Correspondance non vérifiable";
    return (
        <div className={cn("space-y-1", className)}>
            <p className="text-sm">
                <span className="text-muted-foreground">Audio : </span>
                {langs || "langues inconnues"}
                {file.tags.length > 0 && <span className="text-muted-foreground"> · {file.tags.join(" ")}</span>}
            </p>
            {showVerdict && (
                <p className={cn("flex items-center gap-1.5 text-xs font-medium", tone)}>
                    <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                    {verdict}
                </p>
            )}
        </div>
    );
}

/* ── Choix de l'action ─────────────────────────────────────── */

function ActionChoice({
    value,
    onChange,
    options,
}: {
    value: VersionAction;
    onChange: (v: VersionAction) => void;
    options: { value: VersionAction; label: string; desc: string; danger?: boolean }[];
}) {
    return (
        <div role="radiogroup" aria-label="Que faire maintenant" className="space-y-1.5 pt-1">
            {options.map((o) => {
                const active = o.value === value;
                return (
                    <button
                        key={o.value}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        onClick={() => onChange(o.value)}
                        className={cn(
                            "flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
                            active
                                ? o.danger
                                    ? "border-destructive/60 bg-destructive/[0.08]"
                                    : "border-primary/60 bg-primary/[0.1]"
                                : "border-white/[0.06] bg-background/40 hover:bg-white/[0.04]",
                        )}
                    >
                        <span
                            aria-hidden
                            className={cn(
                                "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
                                active ? (o.danger ? "border-destructive" : "border-primary") : "border-white/30",
                            )}
                        >
                            {active && <span className={cn("h-2 w-2 rounded-full", o.danger ? "bg-destructive" : "bg-primary")} />}
                        </span>
                        <span className="min-w-0">
                            <span className={cn("block text-sm font-semibold", active && o.danger && "text-destructive")}>{o.label}</span>
                            <span className="mt-0.5 block text-xs leading-snug text-muted-foreground">{o.desc}</span>
                        </span>
                    </button>
                );
            })}
        </div>
    );
}

/* ── Boîte de dialogue ─────────────────────────────────────── */

export function VersionDialog({
    media,
    open,
    onOpenChange,
    onManualSearch,
}: {
    media: MediaDetail;
    open: boolean;
    onOpenChange: (v: boolean) => void;
    /** Ouvre l'onglet « Releases » (choix manuel d'une release). */
    onManualSearch: () => void;
}) {
    const isMovie = media.type === "movie";
    const arr = isMovie ? "Radarr" : "Sonarr";
    const state = useMediaVersion(media.type, media.id, open);
    const save = useSetMediaVersion();

    const [value, setValue] = useState<PickerValue | null>(null);
    const [action, setAction] = useState<VersionAction>("search");

    // Valeurs de départ = état réel, dès qu'il est connu (une seule fois).
    const data: MediaVersionState | undefined = state.data;
    useEffect(() => {
        if (!data || value) return;
        setValue({
            language: data.version?.language ?? null,
            quality: data.version?.quality ?? data.quality_guess,
            dub: data.version?.dub ?? "any",
        });
        // Rien à relancer si le fichier présent convient déjà.
        setAction(data.file.has_file && data.file.matches === true ? "none" : "search");
    }, [data, value]);

    const hasFile = !!data?.file.has_file;
    const sameVersion =
        !!data?.version &&
        !!value &&
        data.version.language === value.language &&
        data.version.quality === value.quality &&
        data.version.dub === (value.language === "vf" ? value.dub : "any");
    const canSave = !!value?.language && !!value.quality && !(sameVersion && action === "none");

    const actionOptions: { value: VersionAction; label: string; desc: string; danger?: boolean }[] = !isMovie
        ? [
              { value: "search", label: "Chercher maintenant", desc: "Sonarr cherche les épisodes surveillés et remplace ceux pour lesquels il trouve mieux." },
              { value: "none", label: "Plus tard", desc: "Seul le réglage change : il servira aux prochains épisodes et aux mises à niveau." },
          ]
        : hasFile
          ? [
                {
                    value: "search",
                    label: "Chercher une meilleure release",
                    desc: "Le fichier actuel reste en place tant que Radarr n'a pas trouvé mieux. Il peut ne rien remplacer si le fichier actuel est d'une qualité supérieure.",
                },
                {
                    value: "replace",
                    label: "Remplacer maintenant",
                    desc: "Supprime le fichier actuel, puis lance la recherche. Si aucune release ne convient, le film reste manquant jusqu'à ce qu'il en sorte une.",
                    danger: true,
                },
                { value: "none", label: "Garder le fichier pour l'instant", desc: "Seul le réglage change : il servira aux prochaines mises à niveau automatiques." },
            ]
          : [
                { value: "search", label: "Chercher maintenant", desc: "Radarr lance une recherche et télécharge la meilleure release de cette version." },
                { value: "none", label: "Plus tard", desc: "Seul le réglage change : Radarr s'en servira à sa prochaine recherche." },
            ];

    const submit = (then?: () => void, forced?: VersionAction) => {
        if (!value?.language || !value.quality) return;
        const version = { language: value.language, quality: value.quality, dub: value.language === "vf" ? value.dub : ("any" as const) };
        save.mutate(
            { type: media.type, id: media.id, version, action: forced ?? action },
            {
                onSuccess: (r) => {
                    const done =
                        r.action === "replace"
                            ? "Fichier supprimé, recherche lancée."
                            : r.action === "search"
                              ? `Recherche lancée dans ${arr}.`
                              : "Réglage enregistré, rien n'est retéléchargé pour l'instant.";
                    toast.success(`${media.title} : ${versionLabel(r.version)}`, {
                        description: r.profile.created ? `Profil « ${r.profile.name} » créé dans ${arr}. ${done}` : done,
                    });
                    if (r.warnings.length) toast.warning("Profil créé avec des réserves", { description: r.warnings.slice(0, 3).join(" · ") });
                    onOpenChange(false);
                    then?.();
                },
                onError: (e) => toast.error("Changement de version impossible", { description: e.message }),
            },
        );
    };

    return (
        <Dialog open={open} onOpenChange={(o) => !save.isPending && onOpenChange(o)}>
            <DialogContent className="sm:max-w-[560px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 pr-6">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <Languages className="h-4 w-4" />
                        </span>
                        <span className="truncate">Version de « {media.title} »</span>
                    </DialogTitle>
                    <DialogDescription>
                        Choisis la langue et la qualité voulues pour {isMovie ? "ce film" : "cette série"}, indépendamment du reste de ta médiathèque.
                    </DialogDescription>
                </DialogHeader>

                {state.isError ? (
                    <ErrorState compact error={state.error} onRetry={() => state.refetch()} title="Version indisponible" />
                ) : !data || !value ? (
                    <div className="space-y-3 py-1">
                        <Shimmer className="h-16 w-full rounded-xl" />
                        <Shimmer className="h-32 w-full rounded-xl" />
                        <Shimmer className="h-9 w-2/3 rounded-xl" />
                    </div>
                ) : (
                    <div className="space-y-5 py-1">
                        {/* Ce qu'il y a aujourd'hui */}
                        <div className="rounded-xl border border-white/[0.06] bg-background/40 p-3">
                            <p className="text-xs text-muted-foreground">
                                Actuellement :{" "}
                                <span className="font-medium text-foreground">
                                    {data.version ? versionLabel(data.version) : `profil « ${data.profile?.name ?? "inconnu"} »`}
                                </span>
                            </p>
                            <FileVerdict file={data.file} isMovie={isMovie} showVerdict={!!data.version} className="mt-2" />
                        </div>

                        <VersionPicker value={value} onChange={setValue} choices={data.choices} />

                        <fieldset className="space-y-2">
                            <legend className="text-sm font-medium leading-none">{hasFile && isMovie ? "Le fichier déjà téléchargé" : "Et maintenant ?"}</legend>
                            <ActionChoice value={action} onChange={setAction} options={actionOptions} />
                        </fieldset>

                        {!data.monitored && (
                            <p className="flex items-start gap-2 rounded-xl bg-warning/10 p-3 text-xs leading-snug text-warning">
                                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                                {isMovie ? "Ce film n'est pas surveillé" : "Cette série n'est pas surveillée"} : {arr} ne fera aucune mise à niveau automatique plus tard.
                                Active la surveillance dans « ⋯ › Éditer ».
                            </p>
                        )}
                    </div>
                )}

                <DialogFooter className="gap-2 sm:justify-between">
                    <Button
                        variant="ghost"
                        className="text-muted-foreground"
                        disabled={save.isPending || !value?.language || !value.quality}
                        onClick={() => submit(onManualSearch, "none")}
                        title="Enregistre le réglage puis ouvre la liste des releases"
                    >
                        Choisir la release moi-même
                    </Button>
                    <div className="flex flex-col-reverse gap-2 sm:flex-row">
                        <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={save.isPending}>
                            Annuler
                        </Button>
                        <Button variant={action === "replace" ? "destructive" : "default"} onClick={() => submit()} disabled={save.isPending || !canSave}>
                            {save.isPending && <Loader2 className="animate-spin" />}
                            {action === "replace" ? "Supprimer et retélécharger" : action === "search" ? "Enregistrer et chercher" : "Enregistrer"}
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
