import { redirect } from "next/navigation";

/**
 * Ancienne page Assistant (ADR-018) : fondue dans l'Agent IA (ADR-019), qui
 * fait les mêmes actions et en plus diagnostique et répare. L'adresse reste
 * valable (favoris) et renvoie vers l'agent.
 */
export default function AssistantPage() {
    redirect("/copilot");
}
