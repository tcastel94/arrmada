"use client";

/**
 * Paramètres › Agent IA : confirmer chaque action (par défaut), ou laisser
 * l'agent agir seul. Réservé à l'administrateur (la web app). Le même réglage
 * vaut pour l'agent (/copilot) et pour les demandes de l'API /api/ai.
 */
import { Bot, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { useAiSettings, useSetAiMode, type AiMode } from "@/hooks/use-ai-actions";
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
    const choose = (mode: AiMode) =>
        setMode.mutate(mode, {
            onSuccess: () => toast.success(mode === "auto" ? "L'agent agit seul" : "Chaque action sera confirmée"),
            onError: (e) => toast.error("Réglage non enregistré", { description: e.message }),
        });

    return (
        <Panel title="Agent IA" icon={Bot} iconClassName="text-primary" className="h-full" bodyClassName="space-y-2 py-3">
            <p className="text-[13px] text-muted-foreground">
                Avant chaque action de l&apos;agent (débloquer, importer, changer de version, relancer SABnzbd, ajouter un film…). Il ne
                supprime jamais rien de la médiathèque et ne change pas tes réglages.
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
        </Panel>
    );
}
