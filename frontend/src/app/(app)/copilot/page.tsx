"use client";

/**
 * Agent IA (/copilot) : il lit l'état réel de la stack (services, profils,
 * files, journaux, TRaSH Guides, documentation d'ArrMada), trouve la cause
 * d'un problème et le règle, chaque action validée par l'utilisateur
 * (ADR-017, ADR-019). La conversation est dans `hooks/use-copilot.ts`.
 * L'URL reste /copilot pour ne pas casser les favoris.
 */
import { Header } from "@/components/layout/header";
import { PageContainer } from "@/components/shared/page-container";
import { CopilotChat } from "@/components/copilot/copilot-chat";

export default function CopilotPage() {
    return (
        <>
            <Header title="Agent IA" />
            <PageContainer size="narrow" className="space-y-5">
                <CopilotChat />
            </PageContainer>
        </>
    );
}
