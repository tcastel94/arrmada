"use client";

/**
 * Choix de l'équipement facultatif : TV, tablette, ampli, caméras.
 * ----------------------------------------------------------------
 * Utilisé dans l'assistant d'installation (étape « Ton équipement ») et
 * dans Paramètres › Mon équipement. Chaque interrupteur enregistre tout
 * de suite (pas de bouton « Enregistrer » à oublier).
 *
 * Message clé pour un public non technique : RIEN de tout ça n'est
 * obligatoire. Sans TV, sans tablette, sans ampli et sans caméra, ArrMada
 * fait déjà l'essentiel (chercher, télécharger, ranger les films et
 * séries) ; un module éteint disparaît simplement des menus.
 */
import Link from "next/link";
import { ArrowRight, Camera, Loader2, Speaker, Tablet, Tv, type LucideIcon } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/empty-state";
import { MODULE_KEYS, useModules, useSaveModules, type ModuleKey } from "@/hooks/use-modules";
import { cn } from "@/lib/utils";

/** Ce qu'il faut posséder, et où aller ensuite pour le brancher. */
const DETAILS: Record<ModuleKey, { icon: LucideIcon; need: string; next: { href: string; label: string } }> = {
    tv: {
        icon: Tv,
        need: "Une TV Android / Google TV, une Nvidia Shield ou une box avec Kodi.",
        next: { href: "/settings/kodi", label: "Appairer la TV" },
    },
    tablet: {
        icon: Tablet,
        need: "N'importe quelle tablette avec un navigateur web, posée près de la TV.",
        next: { href: "/settings/kodi", label: "Appairer la tablette" },
    },
    amplifier: {
        icon: Speaker,
        need: "Un ampli Yamaha compatible MusicCast, branché au réseau de la maison.",
        next: { href: "/settings/yamaha", label: "Ajouter l'ampli" },
    },
    cameras: {
        icon: Camera,
        need: "Des caméras Eufy et le petit service « eufy-security-ws » sur le serveur.",
        next: { href: "/settings/kodi", label: "Régler les caméras" },
    },
};

export function EquipmentPicker({ showNextLinks = true }: { showNextLinks?: boolean }) {
    const { data, isLoading, isError, error, refetch } = useModules();
    const save = useSaveModules();

    const toggle = (key: ModuleKey, value: boolean) =>
        save.mutate(
            { [key]: value },
            {
                onSuccess: (modules) =>
                    toast.success(value ? `« ${modules[key].label} » activé` : `« ${modules[key].label} » masqué`, {
                        description: value ? "Ses menus et réglages apparaissent." : "Ses menus disparaissent. Tu pourras la réactiver dans Paramètres › Mon équipement.",
                    }),
                onError: (e) => toast.error("Choix non enregistré", { description: e.message }),
            },
        );

    if (isError) return <ErrorState compact error={error} onRetry={() => refetch()} />;

    return (
        <div className="space-y-2.5">
            {MODULE_KEYS.map((key) => {
                const mod = data?.[key];
                const { icon: Icon, need, next } = DETAILS[key];
                const on = !!mod?.enabled;
                const pending = save.isPending && save.variables && key in save.variables;
                return (
                    <div
                        key={key}
                        className={cn(
                            "rounded-2xl border p-4 transition-colors",
                            on ? "border-primary/30 bg-primary/[0.06]" : "border-white/[0.06] bg-white/[0.02]",
                        )}
                    >
                        <label className="flex cursor-pointer items-start gap-3.5">
                            {/* Icône masquée sur téléphone : le texte garde toute la largeur */}
                            <span
                                className={cn(
                                    "hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl sm:flex",
                                    on ? "bg-primary/15 text-primary" : "bg-white/[0.05] text-muted-foreground",
                                )}
                            >
                                <Icon className="h-5 w-5" />
                            </span>
                            <span className="min-w-0 flex-1">
                                {isLoading || !mod ? (
                                    <>
                                        <Shimmer className="h-4 w-36 rounded-md" />
                                        <Shimmer className="mt-2 h-3 w-full rounded-md" />
                                    </>
                                ) : (
                                    <>
                                        <span className="block text-[15px] font-semibold">{mod.label}</span>
                                        <span className="mt-0.5 block text-sm text-muted-foreground">{mod.description}</span>
                                        <span className="mt-1.5 block text-xs text-muted-foreground/80">
                                            <span className="font-medium text-foreground/70">Il te faut :</span> {need}
                                        </span>
                                    </>
                                )}
                            </span>
                            <span className="flex shrink-0 flex-col items-end gap-1 pt-1">
                                {pending ? (
                                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                                ) : (
                                    <Switch
                                        checked={on}
                                        disabled={!mod}
                                        onCheckedChange={(v) => toggle(key, v)}
                                        aria-label={mod?.label ?? key}
                                    />
                                )}
                                <span className="hidden text-[11px] text-muted-foreground sm:block">{on ? "J'en ai" : "Je n'en ai pas"}</span>
                            </span>
                        </label>
                        {showNextLinks && on && (
                            <Link
                                href={next.href}
                                className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-primary hover:opacity-80 sm:ml-[54px]"
                            >
                                {next.label}
                                <ArrowRight className="h-3.5 w-3.5" />
                            </Link>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
