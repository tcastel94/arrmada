"use client";

/**
 * Panneau « Ampli » du Salon : télécommande Yamaha complète, ou bien un
 * état clair si aucun ampli n'est configuré / joignable.
 */
import { Speaker } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EmptyState, ErrorState } from "@/components/shared/empty-state";
import { Shimmer } from "@/components/shared/loading-skeleton";
import { YamahaRemote } from "@/components/yamaha-remote";
import { useYamahaSettings, useYamahaState } from "@/hooks/use-yamaha";

export function AmpPanel() {
    const settings = useYamahaSettings();
    const configured = (settings.data?.length ?? 0) > 0;
    // Même requête que celle de la télécommande (dédupliquée par React Query).
    const state = useYamahaState(configured);

    return (
        <Panel title="Ampli" icon={Speaker} iconClassName="text-orange-300" href={configured ? "/settings/yamaha" : undefined} hrefLabel="Réglages">
            {settings.isLoading || (configured && state.isLoading) ? (
                <div className="space-y-5">
                    <div className="flex items-center gap-3">
                        <Shimmer className="h-10 w-10" />
                        <Shimmer className="h-4 w-32 rounded-md" />
                        <Shimmer className="ml-auto h-12 w-12 rounded-full" />
                    </div>
                    <Shimmer className="mx-auto h-36 w-36 rounded-full" />
                    <Shimmer className="h-3 w-full rounded-full" />
                </div>
            ) : settings.isError ? (
                <ErrorState compact error={settings.error} onRetry={() => settings.refetch()} />
            ) : !configured ? (
                <EmptyState
                    compact
                    icon={Speaker}
                    title="Aucun ampli configuré"
                    description="Ajoute ton ampli Yamaha MusicCast pour régler volume et source d'ici."
                    action={{ label: "Configurer l'ampli", href: "/settings/yamaha" }}
                />
            ) : state.isError ? (
                <ErrorState compact error={state.error} onRetry={() => state.refetch()} title="Ampli injoignable" />
            ) : (
                <YamahaRemote variant="full" card={false} />
            )}
        </Panel>
    );
}
