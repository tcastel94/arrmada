"use client";

/**
 * Raccourcis clavier globaux, façon Gmail/GitHub :
 *   g puis d → Dashboard, g puis m → Médiathèque, etc. (voir lib/nav.ts)
 *   ?        → affiche l'aide
 *   [        → replie / déplie la sidebar
 * Ignorés quand on tape dans un champ de saisie.
 */
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Keyboard } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ALL_NAV_ITEMS } from "@/lib/nav";
import { useModuleEnabled } from "@/hooks/use-modules";
import { useSidebar } from "./sidebar-context";

export function KeyboardShortcuts() {
    const router = useRouter();
    const { toggle } = useSidebar();
    const [helpOpen, setHelpOpen] = useState(false);
    const pendingG = useRef<number | null>(null);
    // Raccourcis des pages d'un équipement absent (pas de TV…) désactivés.
    // Référence tenue à jour pour ne pas réinstaller l'écouteur à chaque rendu.
    const moduleOn = useModuleEnabled();
    const moduleOnRef = useRef(moduleOn);
    moduleOnRef.current = moduleOn;

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            const t = e.target as HTMLElement | null;
            if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) return;
            if (e.metaKey || e.ctrlKey || e.altKey) return;

            if (pendingG.current) {
                window.clearTimeout(pendingG.current);
                pendingG.current = null;
                const target = ALL_NAV_ITEMS.find(
                    (i) => i.shortcut === e.key.toLowerCase() && moduleOnRef.current(i.module),
                );
                if (target) {
                    e.preventDefault();
                    router.push(target.href);
                }
                return;
            }
            if (e.key === "g") {
                pendingG.current = window.setTimeout(() => (pendingG.current = null), 1200);
            } else if (e.key === "?") {
                e.preventDefault();
                setHelpOpen(true);
            } else if (e.key === "[") {
                toggle();
            }
        };
        const openHelp = () => setHelpOpen(true);
        document.addEventListener("keydown", onKey);
        window.addEventListener("open-shortcuts", openHelp);
        return () => {
            document.removeEventListener("keydown", onKey);
            window.removeEventListener("open-shortcuts", openHelp);
        };
    }, [router, toggle]);

    const navShortcuts = ALL_NAV_ITEMS.filter((i) => i.shortcut && moduleOn(i.module));

    return (
        <Dialog open={helpOpen} onOpenChange={setHelpOpen}>
            <DialogContent className="sm:max-w-lg">
                <DialogHeader>
                    <div className="flex items-center gap-3">
                        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30">
                            <Keyboard className="h-5 w-5" />
                        </span>
                        <div>
                            <DialogTitle>Raccourcis clavier</DialogTitle>
                            <DialogDescription>Navigue sans lâcher le clavier, capitaine.</DialogDescription>
                        </div>
                    </div>
                </DialogHeader>
                <div className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
                    <Row label="Recherche / commandes" keys={["⌘", "K"]} />
                    <Row label="Recherche rapide" keys={["/"]} />
                    <Row label="Replier la sidebar" keys={["["]} />
                    <Row label="Cette aide" keys={["?"]} />
                    {navShortcuts.map((i) => (
                        <Row key={i.href} label={i.label} keys={["G", i.shortcut!.toUpperCase()]} />
                    ))}
                </div>
            </DialogContent>
        </Dialog>
    );
}

function Row({ label, keys }: { label: string; keys: string[] }) {
    return (
        <div className="flex items-center justify-between gap-3 border-b border-white/[0.04] py-2 text-sm">
            <span className="text-muted-foreground">{label}</span>
            <span className="flex items-center gap-1">
                {keys.map((k, i) => (
                    <span key={i} className="kbd">
                        {k}
                    </span>
                ))}
            </span>
        </div>
    );
}
