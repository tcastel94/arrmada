"use client";

/**
 * Palette de commandes (⌘K / Ctrl+K, bouton recherche, touche « / »).
 * ----------------------------------------------------------------
 * Trois familles de résultats :
 *  - Médias : recherche live dans la bibliothèque → ouvre DIRECTEMENT la
 *    fiche (avant : renvoyait vers /media?search=… que la page ignorait).
 *  - Pages : toute l'arborescence de lib/nav.ts (avant : liste codée en
 *    dur, incomplète, avec des pages orphelines).
 *  - Actions : synchro Kodi, rafraîchir, tout marquer lu, ajouter un titre…
 */
/* eslint-disable @next/next/no-img-element */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Command as CommandPrimitive } from "cmdk";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
    ArrowRight,
    CheckCheck,
    CornerDownLeft,
    Film,
    Keyboard,
    Loader2,
    LogOut,
    Plus,
    RefreshCw,
    Search,
    Tv,
    MonitorPlay,
    type LucideIcon,
} from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogClose } from "@/components/ui/dialog";
import { useMediaSearch } from "@/hooks/use-media";
import { useDebounce } from "@/hooks/use-debounce";
import { ALL_NAV_ITEMS, findGroupTitle } from "@/lib/nav";
import { apiFetch, logout } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/** Normalise pour une recherche insensible aux accents et à la casse. */
const norm = (s: string) =>
    s
        .toLowerCase()
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "");

interface ActionDef {
    id: string;
    label: string;
    hint?: string;
    icon: LucideIcon;
    keywords: string;
    run: () => void | Promise<void>;
}

export function CommandPalette() {
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const router = useRouter();
    const qc = useQueryClient();
    const debounced = useDebounce(query.trim(), 220);
    const { data: media, isFetching } = useMediaSearch(debounced);

    // Raccourcis d'ouverture : ⌘K / Ctrl+K, « / », et l'évènement custom
    // déclenché par les boutons de recherche (header, sidebar).
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            const target = e.target as HTMLElement | null;
            const typing = target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
            if (e.key.toLowerCase() === "k" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                setOpen((v) => !v);
            } else if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey) {
                e.preventDefault();
                setOpen(true);
            }
        };
        const openViaEvent = () => setOpen(true);
        document.addEventListener("keydown", onKey);
        window.addEventListener("open-command-palette", openViaEvent);
        return () => {
            document.removeEventListener("keydown", onKey);
            window.removeEventListener("open-command-palette", openViaEvent);
        };
    }, []);

    // Remise à zéro à la fermeture.
    useEffect(() => {
        if (!open) setQuery("");
    }, [open]);

    const close = useCallback(() => setOpen(false), []);
    const go = useCallback(
        (href: string) => {
            close();
            router.push(href);
        },
        [close, router],
    );

    const actions: ActionDef[] = useMemo(
        () => [
            {
                id: "add",
                label: query.trim() ? `Ajouter « ${query.trim()} » à la bibliothèque` : "Ajouter un film ou une série",
                hint: "Recherche TMDB/TVDB",
                icon: Plus,
                keywords: "ajouter add nouveau film série request demande",
                run: () => go(query.trim() ? `/search?q=${encodeURIComponent(query.trim())}` : "/search"),
            },
            {
                id: "kodi-sync",
                label: "Synchroniser Kodi",
                hint: "Scan de la bibliothèque Kodi",
                icon: MonitorPlay,
                keywords: "kodi sync scan synchroniser bibliothèque",
                run: async () => {
                    close();
                    const t = toast.loading("Synchronisation Kodi…");
                    try {
                        await apiFetch("/api/kodi/sync", { method: "POST" });
                        toast.success("Synchronisation Kodi lancée", { id: t });
                    } catch (e) {
                        toast.error("Échec de la synchro Kodi", { id: t, description: (e as Error).message });
                    }
                },
            },
            {
                id: "refresh",
                label: "Rafraîchir toutes les données",
                hint: "Vide le cache de l'interface",
                icon: RefreshCw,
                keywords: "refresh rafraichir recharger cache actualiser",
                run: () => {
                    close();
                    qc.invalidateQueries();
                    toast.success("Données rafraîchies");
                },
            },
            {
                id: "read-all",
                label: "Marquer toutes les notifications comme lues",
                icon: CheckCheck,
                keywords: "notifications lues read all",
                run: async () => {
                    close();
                    try {
                        await apiFetch("/api/notifications/read-all", { method: "POST" });
                        qc.invalidateQueries({ queryKey: ["notifications"] });
                        toast.success("Notifications marquées comme lues");
                    } catch (e) {
                        toast.error("Action impossible", { description: (e as Error).message });
                    }
                },
            },
            {
                id: "shortcuts",
                label: "Afficher les raccourcis clavier",
                icon: Keyboard,
                keywords: "raccourcis clavier shortcuts aide help",
                run: () => {
                    close();
                    window.dispatchEvent(new Event("open-shortcuts"));
                },
            },
            {
                id: "logout",
                label: "Se déconnecter",
                icon: LogOut,
                keywords: "logout déconnexion quitter",
                run: () => logout(),
            },
        ],
        [query, go, close, qc],
    );

    const q = norm(query.trim());
    const pages = useMemo(
        () =>
            ALL_NAV_ITEMS.filter(
                (i) =>
                    !q ||
                    norm(`${i.label} ${i.description ?? ""} ${(i.keywords ?? []).join(" ")}`).includes(q),
            ),
        [q],
    );
    const filteredActions = actions.filter((a) => !q || a.id === "add" || norm(`${a.label} ${a.keywords}`).includes(q));
    const mediaItems = debounced.length >= 2 ? media?.items.slice(0, 7) ?? [] : [];

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent className="top-[calc(env(safe-area-inset-top)+0.75rem)] max-h-none gap-0 overflow-hidden p-0 pb-[env(safe-area-inset-bottom)] pt-0 sm:top-[12vh] sm:max-w-2xl sm:translate-y-0 sm:p-0 sm:data-[state=open]:slide-in-from-top-2 sm:data-[state=closed]:slide-out-to-top-2 [&>button]:hidden [&>span:first-child]:hidden">
                <DialogTitle className="sr-only">Palette de commandes</DialogTitle>
                <CommandPrimitive shouldFilter={false} loop className="flex flex-col">
                    {/* Champ de saisie */}
                    <div className="relative flex items-center gap-3 border-b border-white/[0.07] px-4 sm:px-5">
                        <Search className="h-5 w-5 shrink-0 text-muted-foreground" />
                        <CommandPrimitive.Input
                            value={query}
                            onValueChange={setQuery}
                            placeholder="Chercher un média, une page, une action…"
                            className="h-14 flex-1 bg-transparent text-[17px] outline-none placeholder:text-muted-foreground/70"
                        />
                        {isFetching && debounced.length >= 2 && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
                        <span className="kbd hidden sm:inline-flex">Échap</span>
                        {/* Mobile : « Annuler » à droite du champ, comme la recherche iOS */}
                        <DialogClose className="text-[17px] text-primary active:opacity-50 sm:hidden">Annuler</DialogClose>
                        {/* Liseré lumineux sous le champ */}
                    </div>

                    <CommandPrimitive.List className="max-h-[calc(100dvh-8rem)] overflow-y-auto p-2 sm:max-h-[min(60vh,480px)]">
                        <CommandPrimitive.Empty className="py-12 text-center text-sm text-muted-foreground">
                            Aucun résultat pour « {query} »
                        </CommandPrimitive.Empty>

                        {mediaItems.length > 0 && (
                            <Group heading="Médias">
                                {mediaItems.map((m) => (
                                    <Item
                                        key={`${m.type}-${m.external_id}`}
                                        value={`media-${m.type}-${m.external_id}`}
                                        onSelect={() => go(`/media/${m.type}/${m.external_id}`)}
                                    >
                                        <div className="h-11 w-8 shrink-0 overflow-hidden rounded-md bg-muted ring-1 ring-white/10">
                                            {m.poster_url ? (
                                                <img src={m.poster_url} alt="" className="h-full w-full object-cover" loading="lazy" />
                                            ) : (
                                                <div className="flex h-full w-full items-center justify-center">
                                                    {m.type === "movie" ? <Film className="h-3.5 w-3.5" /> : <Tv className="h-3.5 w-3.5" />}
                                                </div>
                                            )}
                                        </div>
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-medium">{m.title}</p>
                                            <p className="text-xs text-muted-foreground">
                                                {m.type === "movie" ? "Film" : "Série"}
                                                {m.year ? ` · ${m.year}` : ""}
                                                {!m.has_file && <span className="text-amber-400"> · manquant</span>}
                                            </p>
                                        </div>
                                        <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-data-[selected=true]:opacity-100" />
                                    </Item>
                                ))}
                            </Group>
                        )}

                        {filteredActions.length > 0 && (
                            <Group heading="Actions">
                                {filteredActions.map((a) => (
                                    <Item key={a.id} value={`action-${a.id}`} onSelect={() => void a.run()}>
                                        <IconTile icon={a.icon} tone={a.id === "add" ? "primary" : "default"} />
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-medium">{a.label}</p>
                                            {a.hint && <p className="text-xs text-muted-foreground">{a.hint}</p>}
                                        </div>
                                    </Item>
                                ))}
                            </Group>
                        )}

                        {pages.length > 0 && (
                            <Group heading="Pages">
                                {pages.map((p) => (
                                    <Item key={p.href} value={`page-${p.href}`} onSelect={() => go(p.href)}>
                                        <IconTile icon={p.icon} />
                                        <div className="min-w-0 flex-1">
                                            <p className="truncate font-medium">
                                                {p.label}
                                                {findGroupTitle(p) && (
                                                    <span className="ml-2 text-[10px] font-normal uppercase tracking-wider text-muted-foreground/60">
                                                        {findGroupTitle(p)}
                                                    </span>
                                                )}
                                            </p>
                                            {p.description && <p className="truncate text-xs text-muted-foreground">{p.description}</p>}
                                        </div>
                                        {p.shortcut && (
                                            <span className="flex shrink-0 items-center gap-1">
                                                <span className="kbd">G</span>
                                                <span className="kbd">{p.shortcut.toUpperCase()}</span>
                                            </span>
                                        )}
                                    </Item>
                                ))}
                            </Group>
                        )}
                    </CommandPrimitive.List>

                    {/* Pied : aide clavier */}
                    <div className="hidden items-center gap-4 border-t border-white/[0.07] px-5 py-2.5 text-[11px] text-muted-foreground sm:flex">
                        <span className="flex items-center gap-1.5">
                            <span className="kbd">↑</span>
                            <span className="kbd">↓</span> naviguer
                        </span>
                        <span className="flex items-center gap-1.5">
                            <span className="kbd">
                                <CornerDownLeft className="h-3 w-3" />
                            </span>
                            ouvrir
                        </span>
                        <span className="ml-auto hidden sm:inline">
                            Astuce : <span className="kbd">/</span> ouvre la recherche partout
                        </span>
                    </div>
                </CommandPrimitive>
            </DialogContent>
        </Dialog>
    );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
    return (
        <CommandPrimitive.Group
            heading={heading}
            className="mb-1 [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:pb-1.5 [&_[cmdk-group-heading]]:pt-2 [&_[cmdk-group-heading]]:text-[13px] [&_[cmdk-group-heading]]:font-semibold [&_[cmdk-group-heading]]:text-muted-foreground"
        >
            {children}
        </CommandPrimitive.Group>
    );
}

function Item({ children, value, onSelect }: { children: React.ReactNode; value: string; onSelect: () => void }) {
    return (
        <CommandPrimitive.Item
            value={value}
            onSelect={onSelect}
            className="group relative flex cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-sm outline-none transition-colors data-[selected=true]:bg-white/[0.08] data-[selected="
        >
            {children}
        </CommandPrimitive.Item>
    );
}

function IconTile({ icon: Icon, tone = "default" }: { icon: LucideIcon; tone?: "default" | "primary" }) {
    return (
        <span
            className={cn(
                "flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ring-1 transition-all group-data-[selected=true]:scale-105",
                tone === "primary"
                    ? "bg-primary/15 text-primary ring-primary/30"
                    : "bg-white/[0.04] text-muted-foreground ring-white/[0.08] group-data-[selected=true]:text-primary group-data-[selected=true]:ring-primary/30",
            )}
        >
            <Icon className="h-4 w-4" />
        </span>
    );
}
