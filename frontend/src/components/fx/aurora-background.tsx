/**
 * Fond global animé de l'application : nappes de lumière (aurora) qui
 * dérivent lentement + grille fine + grain.
 *
 * Choix technique : des radial-gradient (et non des filter: blur) pour
 * rester fluide même sur mobile — seul `transform` est animé, ce que le
 * GPU gère sans recalcul de mise en page.
 */
import { cn } from "@/lib/utils";

export function AuroraBackground({ className, intense = false }: { className?: string; intense?: boolean }) {
    return (
        <div aria-hidden className={cn("pointer-events-none fixed inset-0 -z-10 overflow-hidden", className)}>
            {/* Dégradé de base : nuit profonde, un peu plus claire en haut */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_120%_80%_at_50%_-10%,hsl(222_60%_11%)_0%,hsl(var(--background))_60%)]" />

            {/* Nappes de lumière */}
            <div
                className="absolute -left-[20%] -top-[30%] h-[80vh] w-[80vw] animate-aurora-1 will-change-transform"
                style={{
                    background: `radial-gradient(closest-side, hsl(var(--primary) / ${intense ? 0.32 : 0.18}), transparent 70%)`,
                }}
            />
            <div
                className="absolute -right-[15%] top-[10%] h-[70vh] w-[60vw] animate-aurora-2 will-change-transform"
                style={{
                    background: `radial-gradient(closest-side, hsl(var(--brand) / ${intense ? 0.22 : 0.11}), transparent 70%)`,
                }}
            />
            <div
                className="absolute -bottom-[30%] left-[20%] h-[70vh] w-[70vw] animate-aurora-3 will-change-transform"
                style={{
                    background: `radial-gradient(closest-side, hsl(262 83% 60% / ${intense ? 0.18 : 0.09}), transparent 70%)`,
                }}
            />

            {/* Grille estompée + grain */}
            <div className="absolute inset-0 bg-grid mask-radial opacity-60" />
            <div className="absolute inset-0 bg-noise opacity-[0.035] mix-blend-overlay" />
        </div>
    );
}
