"use client";

/**
 * Paramètres › Agent IA : confirmer chaque action (par défaut), ou laisser
 * l'agent agir seul. Réservé à l'administrateur (la web app). Le même réglage
 * vaut pour l'agent (/copilot) et pour les demandes de l'API /api/ai.
 */
import { Bot, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { Switch } from "@/components/ui/switch";
import { useAiSettings, useSetAiMode, useSetTelegramAlerts, type AiMode } from "@/hooks/use-ai-actions";
import { cn } from "@/lib/utils";

const CHOICES: { value: AiMode; label: string; help: string }[] = [
    {
        value: "confirm",
        label: "Confirmer chaque action",
        help: "L'agent montre ce qu'il va faire (« Débloquer Dune ? »), rien ne se fait sans ton clic. Recommandé.",
    },
    {
        value: "auto",
        label: "Agir tout de suite",
        help: "L'agent exécute ses actions et rend compte. Plus rapide, mais une erreur de cible agit pour de vrai.",
    },
];

export function AssistantPanel() {
    const { data } = useAiSettings();
    const setMode = useSetAiMode();
    const setAlerts = useSetTelegramAlerts();
    const telegram = data?.telegram;
    const choose = (mode: AiMode) =>
        setMode.mutate(mode, {
            onSuccess: () => toast.success(mode === "auto" ? "L'agent agit seul" : "Chaque action sera confirmée"),
            onError: (e) => toast.error("Réglage non enregistré", { description: e.message }),
        });

    return (
        <Panel title="Agent IA" icon={Bot} iconClassName="text-primary" className="h-full" bodyClassName="space-y-2 py-3">
            <p className="text-[13px] text-muted-foreground">
                Avant chaque action de l&apos;agent (débloquer, importer, changer de version, relancer SABnzbd, ajouter un film, modifier un
                profil qualité, remplacer un remux…). Il ne supprime aucun titre ; le seul fichier qu&apos;il retire est un remux qu&apos;il fait
                remplacer par une version plus légère. Côté réglages, il ne touche qu&apos;aux profils qualité.
            </p>
            <div className="grid gap-2" role="radiogroup" aria-label="Validation des actions de l'agent">
                {CHOICES.map((c) => {
                    const on = data?.mode === c.value;
                    return (
                        <button
                            key={c.value}
                            type="button"
                            role="radio"
                            aria-checked={on}
                            onClick={() => !on && choose(c.value)}
                            disabled={setMode.isPending}
                            className={cn(
                                "rounded-xl border p-3 text-left transition-colors",
                                on ? "border-primary/60 bg-primary/10" : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.05]",
                            )}
                        >
                            <span className="flex items-center gap-2 text-[14px] font-semibold">
                                {setMode.isPending && setMode.variables === c.value && <Loader2 className="h-4 w-4 animate-spin" />}
                                {c.label}
                            </span>
                            <span className="mt-0.5 block text-[12.5px] text-muted-foreground">{c.help}</span>
                        </button>
                    );
                })}
            </div>

            {/* Alertes Telegram : un téléchargement bloqué arrive sur le téléphone avec ses boutons */}
            <div className="flex items-start justify-between gap-3 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">
                <div className="min-w-0">
                    <p className="text-[14px] font-semibold">Alertes Telegram des blocages</p>
                    <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                        {telegram?.configured === false
                            ? "Telegram n'est pas configuré : renseigne TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans le .env."
                            : "Un téléchargement bloqué depuis 10 minutes t'est envoyé avec son diagnostic et les boutons « Débloquer » / « Ignorer ». En mode « agir tout de suite », il est débloqué et tu reçois le résultat."}
                    </p>
                </div>
                <Switch
                    checked={Boolean(telegram?.configured && telegram.alerts)}
                    disabled={!telegram?.configured || setAlerts.isPending}
                    onCheckedChange={(on) =>
                        setAlerts.mutate(on, {
                            onSuccess: () => toast.success(on ? "Alertes Telegram activées" : "Alertes Telegram coupées"),
                            onError: (e) => toast.error("Réglage non enregistré", { description: e.message }),
                        })
                    }
                    aria-label="Alertes Telegram des téléchargements bloqués"
                />
            </div>
        </Panel>
    );
}
