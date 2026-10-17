"use client";

/**
 * Paramètres → Auto-configuration.
 * ----------------------------------------------------------------
 * Lit les clés API dans les fichiers de config des applis (dossier
 * appdata monté en lecture seule) et les branche entre elles. Tout le
 * travail est fait par <StackWiring /> ; la page ajoute l'explication et
 * rafraîchit la liste des services une fois le plan appliqué.
 */
import { useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { StackWiring } from "@/components/stack/stack-wiring";

export default function AutoconfigPage() {
    const queryClient = useQueryClient();
    return (
        <>
            <Panel title="Câblage automatique de la stack" icon={Wand2} iconClassName="text-primary">
                <StackWiring
                    onApplied={(results) => {
                        const ok = results.filter((r) => r.ok).length;
                        const ko = results.length - ok;
                        if (ko === 0) toast.success(`${ok} action(s) appliquée(s)`);
                        else toast.warning(`${ok} réussie(s), ${ko} en échec — détail dans la liste`);
                        // Nouveaux services enregistrés → listes et tableaux de bord à jour.
                        void queryClient.invalidateQueries();
                    }}
                />
            </Panel>
            <p className="flex items-start gap-2 px-1 text-xs text-muted-foreground">
                <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                Les clés et mots de passe restent sur le serveur ArrMada : ton navigateur ne voit que « clé trouvée ».
                Le dossier appdata est lu, jamais modifié. Chaque ajout est testé par l&apos;appli concernée avant
                d&apos;être enregistré, et relancer ne crée jamais de doublon.
            </p>
        </>
    );
}
