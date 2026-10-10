"use client";

/**
 * Onglet « Imports » de /downloads (remplace l'ancienne page /fichiers,
 * qui redirige ici via next.config.mjs).
 * ----------------------------------------------------------------
 *   1. Imports bloqués (action principale de la page) ;
 *   2. Chemins NAS ;
 *   3. Historique, au choix : SABnzbd ou auto-import (`?historique=auto`).
 *      Seule la section choisie est montée → le rafraîchissement 30 s de
 *      l'auto-import ne tourne que si on la regarde.
 */
import { motion } from "framer-motion";
import { Bot, History } from "lucide-react";
import { useUrlState } from "@/hooks/use-url-state";
import { Segmented } from "@/components/activity/segmented";
import { fadeUp, stagger } from "@/lib/motion";
import { StuckImports } from "./stuck-imports";
import { NasPaths } from "./nas-paths";
import { SabHistory } from "./sab-history";
import { AutoImportReports } from "./auto-import-reports";

type HistorySection = "sab" | "auto";

export function ImportsTab() {
    const [section, setSection] = useUrlState<HistorySection>("historique", "sab");

    return (
        <motion.div variants={stagger(0, 0.08)} initial="hidden" animate="show" className="space-y-6">
            <motion.div variants={fadeUp}>
                <StuckImports />
            </motion.div>

            <motion.div variants={fadeUp}>
                <NasPaths />
            </motion.div>

            <motion.section variants={fadeUp} className="space-y-3" aria-label="Historique">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <p className="eyebrow">Historique</p>
                        <h2 className="text-base font-semibold tracking-tight">
                            {section === "sab" ? "Téléchargements SABnzbd" : "Auto-import périodique"}
                        </h2>
                    </div>
                    <Segmented<HistorySection>
                        ariaLabel="Choisir l'historique"
                        value={section === "auto" ? "auto" : "sab"}
                        onChange={setSection}
                        options={[
                            { value: "sab", label: "SABnzbd", icon: History },
                            { value: "auto", label: "Auto-import", icon: Bot, tone: "text-emerald-300" },
                        ]}
                    />
                </div>
                {section === "auto" ? <AutoImportReports /> : <SabHistory />}
            </motion.section>
        </motion.div>
    );
}
