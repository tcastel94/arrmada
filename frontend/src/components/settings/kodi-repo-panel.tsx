"use client";

/**
 * Réglages → Kodi → « Mises à jour de l'appli Kodi » (ADR-003 § 5).
 * ----------------------------------------------------------------
 * ArrMada sert un dépôt Kodi (`/kodi/repo/`). Une fois le dépôt installé sur
 * la TV, Kodi met l'appli à jour tout seul : plus de zip à copier.
 * Le panneau affiche l'adresse exacte à saisir dans Kodi et la version servie.
 *
 * Pas de bouton « Copier » : sur une adresse http:// du réseau local, le
 * navigateur interdit l'accès au presse-papiers. L'adresse se sélectionne
 * d'un clic (select-all).
 */
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, PackageCheck, RefreshCw } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { apiFetch } from "@/lib/api-client";

interface KodiRepoInfo {
    addon_id: string;
    addon_version: string;
    repository_version: string;
    /** Adresse du dépôt telle que vue depuis ce navigateur. */
    repo_url: string;
}

export function KodiRepoPanel() {
    const { data, isLoading, isError, error } = useQuery<KodiRepoInfo>({
        queryKey: ["kodi", "repo"],
        queryFn: () => apiFetch("/kodi/repo/info.json"),
        staleTime: 5 * 60_000,
        retry: false,
    });

    return (
        <Panel
            title="Mises à jour de l'appli Kodi"
            icon={PackageCheck}
            iconClassName="text-emerald-300"
            action={
                data ? (
                    <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                        v{data.addon_version} servie
                    </span>
                ) : undefined
            }
            bodyClassName="space-y-4"
        >
            <p className="text-xs leading-relaxed text-muted-foreground">
                ArrMada sert un dépôt Kodi : installe-le une fois sur chaque TV, puis Kodi met l&apos;appli à jour tout seul (au
                démarrage puis toutes les 24 h).
            </p>

            {isLoading ? (
                <Shimmer className="h-10 w-full rounded-xl" />
            ) : isError || !data ? (
                <div className="flex gap-2.5 rounded-xl border border-amber-500/25 bg-amber-500/[0.06] p-3 text-xs leading-relaxed text-amber-200">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                    <div>
                        <p className="font-semibold">Dépôt indisponible</p>
                        <p className="text-amber-200/80">
                            {error instanceof Error ? error.message : "Le serveur ne répond pas."} Le conteneur backend doit voir le
                            dossier <code className="font-mono">kodi-addon</code> : ligne{" "}
                            <code className="font-mono">./kodi-addon:/app/kodi-addon:ro</code> dans docker-compose.yml, puis{" "}
                            <code className="font-mono">./deploy.sh --backend</code>.
                        </p>
                    </div>
                </div>
            ) : (
                <>
                    <div className="space-y-1.5">
                        <p className="text-xs text-muted-foreground">Adresse à saisir dans Kodi</p>
                        <p className="select-all break-all rounded-xl border border-white/[0.06] bg-background/40 px-3 py-2.5 font-mono text-sm text-foreground">
                            {data.repo_url}
                        </p>
                    </div>
                    {/* Incident 1.7.0, corrigé le 17/10/2026 : Kodi lit un zip de la source http://
                        par morceaux (requêtes Range) ; le serveur les ignorait et Kodi plantait.
                        Le journal d'un Kodi fermé net arrive tout seul sur le serveur (appli 1.21.1). */}
                    <p className="text-[11px] leading-relaxed text-muted-foreground">
                        Si Kodi se ferme pendant une installation, son journal arrive tout seul sur le serveur au
                        démarrage suivant (<code className="font-mono">data/kodi-crashes/</code>).
                    </p>
                    <ol className="list-inside list-decimal space-y-1 text-xs leading-relaxed text-muted-foreground">
                        <li>
                            Paramètres → Système → Extensions : active <span className="text-foreground">« Sources inconnues »</span>.
                        </li>
                        <li>
                            Gestionnaire de fichiers → <span className="text-foreground">Ajouter une source</span> → l&apos;adresse
                            ci-dessus, nomme-la « ArrMada ».
                        </li>
                        <li>
                            Extensions → <span className="text-foreground">Installer depuis un fichier zip</span> → ArrMada →{" "}
                            <span className="font-mono text-foreground">repository.arrmada.zip</span>.
                        </li>
                        <li>
                            Extensions → <span className="text-foreground">Installer depuis un dépôt</span> → Dépôt ArrMada → ArrMada
                            (déjà installée : rien à faire, la mise à jour arrive seule).
                        </li>
                    </ol>
                    <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        <RefreshCw className="h-3 w-3" />
                        Pour forcer la vérification : Extensions → Mes extensions → Dépôts d&apos;extensions → Dépôt ArrMada → Mettre à
                        jour.
                    </p>
                </>
            )}
        </Panel>
    );
}
