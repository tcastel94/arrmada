"use client";

/**
 * Copilote (/copilot) : assistant IA qui lit l'état réel de la stack
 * (services, profils, files, journaux, TRaSH Guides, documentation d'ArrMada)
 * avant de conseiller. Lecture seule : il explique et anticipe, il ne modifie
 * rien (ADR-017). La conversation est dans `hooks/use-copilot.ts`.
 */
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { CopilotChat } from "@/components/copilot/copilot-chat";

export default function CopilotPage() {
    return (
        <>
            <Header title="Copilote" />
            <PageContainer size="narrow" className="space-y-5">
                <CopilotChat />
            </PageContainer>
        </>
    );
}
