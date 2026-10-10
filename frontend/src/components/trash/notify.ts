/**
 * Toast décrivant le résultat de l'application d'un override de profil
 * (partagé par la liste et la boîte d'ajout).
 */
import { toast } from "sonner";
import type { ApplyOverrideResult } from "@/hooks/use-profile-overrides";
import { plural } from "@/lib/format";

export function notifyApplyResult(title: string, profile: string, res: ApplyOverrideResult) {
    if (res.success && res.media_updated) {
        toast.success(`« ${title} » utilise maintenant « ${profile} »`, {
            description: `${plural(res.cfs_created, "format créé", "formats créés")}, ${plural(res.cfs_updated, "format mis à jour", "formats mis à jour")}.`,
        });
    } else if (res.success) {
        toast.warning(`Profil prêt mais « ${title} » n'a pas été basculé`, {
            description: "Le profil a été créé/mis à jour ; vérifie le média dans Sonarr/Radarr.",
        });
    } else {
        toast.error(`Échec de l'application pour « ${title} »`, { description: res.errors[0] });
    }
}

