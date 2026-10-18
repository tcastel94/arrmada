"use client";

/**
 * Briques des barres d'outils de la Bibliothèque.
 * ----------------------------------------------------------------
 *  - StickyToolbar     : barre en verre collée sous le header au défilement
 *  - SearchField       : champ de recherche avec icône, spinner et bouton ✕
 *  - RemovableChip     : filtre actif supprimable d'un clic
 *  - FilterPresetsMenu : « filtres enregistrés » (préréglages nommés)
 */
import { forwardRef, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { toast } from "sonner";
import { Bookmark, BookmarkCheck, BookmarkPlus, Check, Loader2, Search, Trash2, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { EASE_OUT, SPRING } from "@/lib/motion";
import {
    MAX_PRESETS,
    PRESETS_STORAGE_KEY,
    describeParams,
    describeParts,
    isEmptyParams,
    loadPresets,
    newPresetId,
    sameParams,
    savePresets,
    type FilterPreset,
    type PresetParams,
} from "@/lib/media-filters";

/**
 * Barre collante sous le header (68 px + marge). Sur mobile elle reste dans
 * le flux (non collante) pour ne pas manger la moitié de l'écran.
 */
export function StickyToolbar({ children, className }: { children: ReactNode; className?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.1 }}
            className={cn(
                "glass z-20 rounded-2xl p-2 shadow-[0_18px_40px_-24px_rgba(0,0,0,0.9)] sm:sticky sm:top-[84px]",
                className,
            )}
        >
            {children}
        </motion.div>
    );
}

interface SearchFieldProps {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    /** Affiche un spinner à droite (requête en cours). */
    loading?: boolean;
    onSubmit?: () => void;
    size?: "md" | "lg";
    autoFocus?: boolean;
    ariaLabel: string;
    className?: string;
    id?: string;
}

export const SearchField = forwardRef<HTMLInputElement, SearchFieldProps>(function SearchField(
    { value, onChange, placeholder, loading, onSubmit, size = "md", autoFocus, ariaLabel, className, id },
    ref,
) {
    const lg = size === "lg";
    return (
        <div className={cn("relative min-w-0", className)}>
            <Search
                aria-hidden
                className={cn(
                    "pointer-events-none absolute top-1/2 -translate-y-1/2 text-muted-foreground/60",
                    lg ? "left-4 h-5 w-5" : "left-3 h-4 w-4",
                )}
            />
            <Input
                ref={ref}
                id={id}
                type="search"
                value={value}
                autoFocus={autoFocus}
                aria-label={ariaLabel}
                placeholder={placeholder}
                onChange={(e) => onChange(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === "Enter") onSubmit?.();
                    if (e.key === "Escape" && value) {
                        e.preventDefault();
                        onChange("");
                    }
                }}
                className={cn(
                    // Masque la croix native du type=search (on a la nôtre).
                    "[&::-webkit-search-cancel-button]:appearance-none",
                    lg ? "h-14 rounded-2xl pl-12 pr-12 text-base md:text-lg" : "h-9 pl-9 pr-9",
                )}
            />
            <div className={cn("absolute top-1/2 flex -translate-y-1/2 items-center", lg ? "right-3" : "right-2")}>
                {loading ? (
                    <Loader2 className={cn("animate-spin text-primary", lg ? "h-5 w-5" : "h-4 w-4")} aria-label="Recherche en cours" />
                ) : value ? (
                    <motion.button
                        type="button"
                        initial={{ scale: 0.5, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        transition={SPRING}
                        onClick={() => onChange("")}
                        aria-label="Effacer la recherche"
                        className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-white/10 hover:text-foreground"
                    >
                        <X className={lg ? "h-4 w-4" : "h-3.5 w-3.5"} />
                    </motion.button>
                ) : null}
            </div>
        </div>
    );
});

/** Chip de filtre actif : cliquer dessus retire le filtre. */
export function RemovableChip({ label, onRemove }: { label: ReactNode; onRemove: () => void }) {
    return (
        <motion.button
            layout
            type="button"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={SPRING}
            onClick={onRemove}
            data-active="true"
            className="chip group"
            aria-label={`Retirer le filtre ${typeof label === "string" ? label : ""}`.trim()}
        >
            {label}
            <X className="h-3 w-3 opacity-60 transition-opacity group-hover:opacity-100" />
        </motion.button>
    );
}

/* ════════════════════════════════════════════════════════════════
   Filtres enregistrés
   ════════════════════════════════════════════════════════════════ */

/** Longueur max d'un nom de préréglage (le menu reste lisible). */
const PRESET_NAME_MAX = 40;

/**
 * Menu « Enregistrés » : enregistre le jeu de filtres courant sous un nom,
 * l'applique en un clic, le supprime (avec « Annuler » dans le toast).
 * ----------------------------------------------------------------
 * Le composant ne connaît que des paramètres d'URL (`current`) : c'est la
 * page qui sait comment les appliquer (`onApply` → réécriture de l'URL).
 * Les préréglages vivent dans le localStorage de CE navigateur (voir
 * lib/media-filters) et sont relus si un autre onglet les modifie.
 */
export function FilterPresetsMenu({
    current,
    onApply,
    className,
}: {
    /** Filtres actuellement appliqués (instantané de l'URL). */
    current: PresetParams;
    onApply: (preset: FilterPreset) => void;
    className?: string;
}) {
    // Lu après le montage (le stockage n'existe pas côté serveur : lire au
    // premier rendu provoquerait un écart d'hydratation).
    const [presets, setPresets] = useState<FilterPreset[]>([]);
    // Copie toujours à jour, lue par le « Annuler » du toast (qui peut être
    // cliqué bien après la suppression, quand `presets` a encore changé).
    const presetsRef = useRef<FilterPreset[]>([]);
    const replace = useCallback((next: FilterPreset[]) => {
        presetsRef.current = next;
        setPresets(next);
    }, []);

    useEffect(() => {
        replace(loadPresets());
        // Synchro entre onglets : l'événement `storage` n'est émis que dans
        // les AUTRES onglets que celui qui écrit.
        const onStorage = (e: StorageEvent) => {
            if (e.key === PRESETS_STORAGE_KEY || e.key === null) replace(loadPresets());
        };
        window.addEventListener("storage", onStorage);
        return () => window.removeEventListener("storage", onStorage);
    }, [replace]);

    /** Met à jour l'état + le stockage ; prévient si le navigateur refuse. */
    const persist = useCallback(
        (next: FilterPreset[]) => {
            replace(next);
            if (!savePresets(next)) {
                toast.error("Impossible d'enregistrer tes filtres", {
                    description: "Ton navigateur bloque le stockage local (navigation privée ?). Ils seront perdus à la fermeture.",
                });
                return false;
            }
            return true;
        },
        [replace],
    );

    const active = presets.find((p) => sameParams(p.params, current));
    const noFilter = isEmptyParams(current);

    /* ── Suppression (annulable) ── */
    const remove = (preset: FilterPreset) => {
        const index = presetsRef.current.findIndex((p) => p.id === preset.id);
        persist(presetsRef.current.filter((p) => p.id !== preset.id));
        toast.success(`Filtre « ${preset.name} » supprimé`, {
            action: {
                label: "Annuler",
                onClick: () => {
                    const list = presetsRef.current.filter((p) => p.id !== preset.id);
                    list.splice(Math.max(0, Math.min(index, list.length)), 0, preset);
                    persist(list);
                },
            },
        });
    };

    /* ── Enregistrement (boîte de dialogue) ── */
    const [saveOpen, setSaveOpen] = useState(false);
    const [name, setName] = useState("");
    // Le menu se ferme en rendant le focus à son bouton : on l'en empêche
    // quand c'est pour ouvrir la boîte (sinon le champ « Nom » perd le focus).
    const openingDialog = useRef(false);

    const openSave = () => {
        openingDialog.current = true;
        // Nom proposé : le résumé des filtres, que tu peux garder ou raccourcir.
        setName(describeParams(current).slice(0, PRESET_NAME_MAX));
        setSaveOpen(true);
    };

    const trimmed = name.trim();
    const existing = presets.find((p) => p.name.toLowerCase() === trimmed.toLowerCase());
    const duplicate = presets.find((p) => p.id !== existing?.id && sameParams(p.params, current));

    const submit = (e: FormEvent) => {
        e.preventDefault();
        if (!trimmed) return;
        if (!existing && presets.length >= MAX_PRESETS) {
            toast.error(`${MAX_PRESETS} filtres enregistrés au maximum`, { description: "Supprimes-en un pour faire de la place." });
            return;
        }
        // Même nom → on remplace (en gardant sa place dans la liste).
        const next = existing
            ? presets.map((p) => (p.id === existing.id ? { ...p, name: trimmed, params: current } : p))
            : [...presets, { id: newPresetId(), name: trimmed, params: current, createdAt: Date.now() }];
        if (persist(next)) toast.success(existing ? `Filtre « ${trimmed} » mis à jour` : `Filtre « ${trimmed} » enregistré`);
        setSaveOpen(false);
    };

    return (
        <>
            {/* modal={false} : sinon Radix peut laisser <body> non cliquable quand un item ouvre une boîte de dialogue. */}
            <DropdownMenu modal={false}>
                <DropdownMenuTrigger asChild>
                    <Button
                        variant="outline"
                        className={cn("max-w-[13rem]", active && "border-primary/40 text-primary", className)}
                        aria-label={active ? `Filtres enregistrés (actif : ${active.name})` : "Filtres enregistrés"}
                        title={active ? `Filtre enregistré appliqué : ${active.name}` : "Filtres enregistrés"}
                    >
                        {active ? <BookmarkCheck /> : <Bookmark />}
                        {/* Le nom du préréglage actif remplace le libellé : on voit ce qui est appliqué. */}
                        <span className="hidden truncate sm:inline">{active ? active.name : "Enregistrés"}</span>
                        {!active && presets.length > 0 && (
                            <span className="hidden rounded-full bg-white/10 px-1.5 text-[10px] font-semibold tabular-nums text-muted-foreground sm:inline">
                                {presets.length}
                            </span>
                        )}
                    </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                    align="end"
                    className="w-[min(20rem,calc(100vw-2rem))]"
                    onCloseAutoFocus={(e) => {
                        if (openingDialog.current) {
                            e.preventDefault();
                            openingDialog.current = false;
                        }
                    }}
                >
                    <DropdownMenuLabel className="eyebrow">Filtres enregistrés</DropdownMenuLabel>
                    {presets.length === 0 ? (
                        <div className="flex flex-col items-center gap-1.5 px-3 py-4 text-center text-xs text-muted-foreground">
                            <Bookmark className="h-5 w-5 opacity-40" aria-hidden />
                            Règle tes filtres, puis enregistre-les ici pour les retrouver en un clic.
                        </div>
                    ) : (
                        <AnimatePresence initial={false}>
                            {presets.map((p) => {
                                const isActive = active?.id === p.id;
                                return (
                                    <motion.div
                                        key={p.id}
                                        layout
                                        exit={{ opacity: 0, height: 0 }}
                                        transition={{ duration: 0.2, ease: EASE_OUT }}
                                        className="flex items-center gap-0.5"
                                    >
                                        {/* Deux items côte à côte : le second (supprimer) reste
                                            atteignable au clavier avec les flèches. */}
                                        <DropdownMenuItem onSelect={() => onApply(p)} className="min-w-0 flex-1 items-start">
                                            <Check className={cn("mt-0.5 text-primary", !isActive && "opacity-0")} aria-hidden />
                                            <span className="min-w-0">
                                                <span className={cn("block truncate font-medium", isActive && "text-primary")}>{p.name}</span>
                                                <span className="block truncate text-[11px] text-muted-foreground">{describeParams(p.params)}</span>
                                            </span>
                                        </DropdownMenuItem>
                                        <DropdownMenuItem
                                            onSelect={(e) => {
                                                // Le menu reste ouvert : on peut en supprimer plusieurs d'affilée.
                                                e.preventDefault();
                                                remove(p);
                                            }}
                                            aria-label={`Supprimer le filtre « ${p.name} »`}
                                            title="Supprimer"
                                            className="shrink-0 self-stretch px-2 text-muted-foreground focus:bg-red-500/10 focus:text-red-300"
                                        >
                                            <Trash2 />
                                        </DropdownMenuItem>
                                    </motion.div>
                                );
                            })}
                        </AnimatePresence>
                    )}
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onSelect={openSave} disabled={noFilter} className="text-primary">
                        <BookmarkPlus />
                        Enregistrer les filtres actuels…
                    </DropdownMenuItem>
                    {noFilter && <p className="px-2 pb-1.5 text-[11px] text-muted-foreground/80">Aucun filtre actif pour l&apos;instant.</p>}
                </DropdownMenuContent>
            </DropdownMenu>

            <Dialog open={saveOpen} onOpenChange={setSaveOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <BookmarkPlus className="h-5 w-5 text-primary" aria-hidden />
                            Enregistrer ces filtres
                        </DialogTitle>
                        <DialogDescription>Tu les retrouveras en un clic dans « Enregistrés », sur ce navigateur.</DialogDescription>
                    </DialogHeader>
                    <form onSubmit={submit} className="space-y-4">
                        <div className="flex flex-wrap gap-1.5 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                            {describeParts(current).map((part, i) => (
                                <span key={`${i}:${part}`} className="chip" data-active="true">
                                    {part}
                                </span>
                            ))}
                        </div>
                        <div className="space-y-1.5">
                            <Label htmlFor="preset-name">Nom</Label>
                            <Input
                                id="preset-name"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                onFocus={(e) => e.currentTarget.select()}
                                maxLength={PRESET_NAME_MAX}
                                placeholder="Ex : Films 4K non vus"
                                autoComplete="off"
                                autoFocus
                            />
                            {existing ? (
                                <p className="text-[11px] text-amber-400">Un filtre porte déjà ce nom : il sera remplacé.</p>
                            ) : duplicate ? (
                                <p className="text-[11px] text-muted-foreground">Ces filtres sont déjà enregistrés sous « {duplicate.name} ».</p>
                            ) : null}
                        </div>
                        <DialogFooter className="gap-2">
                            <Button type="button" variant="ghost" onClick={() => setSaveOpen(false)}>
                                Annuler
                            </Button>
                            <Button type="submit" disabled={!trimmed}>
                                <BookmarkPlus />
                                {existing ? "Remplacer" : "Enregistrer"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </>
    );
}
