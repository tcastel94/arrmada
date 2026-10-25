"use client";

/**
 * Paramètres → Mon équipement.
 * ----------------------------------------------------------------
 * Active seulement ce que la maison possède (TV avec l'appli, tablette,
 * ampli Yamaha, caméras Eufy). Un module éteint disparaît des menus, des
 * réglages et n'interroge plus rien en tâche de fond.
 * En dessous : la liste « Ce qu'il te reste à faire », à revoir à tout
 * moment (pas seulement pendant l'assistant).
 */
import { ListChecks, PackageCheck } from "lucide-react";
import { Panel } from "@/components/shared/panel";
import { EquipmentPicker } from "@/components/setup/equipment-picker";
import { SetupChecklist } from "@/components/setup/setup-checklist";

export default function EquipmentPage() {
    return (
        <>
            <Panel title="Mon équipement" icon={PackageCheck}>
                <p className="mb-4 text-sm text-muted-foreground">
                    Rien de tout ça n&apos;est obligatoire : sans TV, tablette, ampli ni caméra, ArrMada cherche, télécharge
                    et range déjà tes films et séries. Active seulement ce que tu possèdes.
                </p>
                <EquipmentPicker />
            </Panel>
            <Panel title="Ce qu'il te reste à faire" icon={ListChecks}>
                <SetupChecklist />
            </Panel>
        </>
    );
}
