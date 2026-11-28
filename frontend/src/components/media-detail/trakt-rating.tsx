"use client";

/**
 * « Ma note Trakt » sur la fiche d'un film ou d'une série (ADR-022).
 * ----------------------------------------------------------------
 * 5 étoiles, demi-étoiles (les 10 niveaux de Trakt) : la moitié gauche d'une
 * étoile donne la demi-étoile, la moitié droite l'étoile pleine. Le survol
 * montre la note avant de cliquer. Plusieurs profils reliés : on choisit
 * pour qui l'on note (le dernier choix est retenu sur ce navigateur).
 * Rien ne s'affiche si aucun profil n'a de compte Trakt.
 */
import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { useTraktAccounts, useTraktRate, useTraktRatings, type TraktTarget } from "@/hooks/use-trakt";
import { cn } from "@/lib/utils";

const LABELS = ["", "Nul", "Très mauvais", "Mauvais", "Bof", "Moyen", "Correct", "Bien", "Très bien", "Excellent", "Chef-d'œuvre"];
const STORE = "arrmada.trakt.profile";

function readStored(): number | null {
    try {
        const raw = window.localStorage.getItem(STORE);
        return raw === null ? null : Number(raw);
    } catch {
        return null;
    }
}

function stars(rating: number) {
    return rating % 2 === 0 ? String(rating / 2) : `${Math.floor(rating / 2)},5`;
}

export function TraktRating({ target }: { target: TraktTarget }) {
    const accounts = useTraktAccounts();
    const linked = (accounts.data?.profiles ?? []).filter((p) => p.linked);
    const [chosen, setChosen] = useState<number | null>(() => (typeof window === "undefined" ? null : readStored()));
    const profileKey = linked.some((p) => p.profile_key === chosen) ? chosen : (linked[0]?.profile_key ?? null);
    const ratings = useTraktRatings(target, profileKey);
    const rate = useTraktRate(target, profileKey);
    const [hover, setHover] = useState(0);

    if (!accounts.data?.configured || linked.length === 0 || !(target.tmdbId || target.tvdbId)) return null;

    const current = (target.kind === "movie" ? ratings.data?.movie : ratings.data?.show) ?? 0;
    const shown = hover || current;
    const send = (value: number) =>
        rate.mutate(value, {
            onSuccess: (r) => toast.success(r.message),
            onError: (e) => toast.error("Note non envoyée", { description: e.message }),
        });
    const pick = (key: number) => {
        setChosen(key);
        try {
            window.localStorage.setItem(STORE, String(key));
        } catch {
            // navigation privée : le choix ne sera simplement pas retenu
        }
    };

    return (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5" aria-label="Ma note Trakt">
            <span className="text-[13px] font-medium text-muted-foreground">Ma note Trakt</span>
            {linked.length > 1 && (
                <div className="flex gap-1" role="radiogroup" aria-label="Profil qui note">
                    {linked.map((p) => (
                        <button
                            key={p.profile_key}
                            type="button"
                            role="radio"
                            aria-checked={p.profile_key === profileKey}
                            onClick={() => pick(p.profile_key)}
                            className={cn(
                                "rounded-full px-2.5 py-0.5 text-[12px] font-medium transition-colors",
                                p.profile_key === profileKey ? "bg-primary/20 text-primary" : "bg-white/[0.05] text-muted-foreground hover:bg-white/[0.08]",
                            )}
                        >
                            {p.name}
                        </button>
                    ))}
                </div>
            )}
            <div className="flex items-center" onMouseLeave={() => setHover(0)} role="group" aria-label="Étoiles">
                {[0, 1, 2, 3, 4].map((i) => {
                    const fill = shown >= (i + 1) * 2 ? 1 : shown === i * 2 + 1 ? 0.5 : 0;
                    return (
                        <span key={i} className="relative inline-block h-6 w-6 text-[22px] leading-6">
                            <span className="absolute inset-0 text-white/20" aria-hidden>
                                ★
                            </span>
                            <span className="absolute inset-0 overflow-hidden text-[#FFC93C]" style={{ width: `${fill * 100}%` }} aria-hidden>
                                ★
                            </span>
                            {/* Moitié gauche : demi-étoile ; moitié droite : étoile pleine */}
                            {[i * 2 + 1, i * 2 + 2].map((value, half) => (
                                <button
                                    key={value}
                                    type="button"
                                    disabled={rate.isPending || profileKey === null}
                                    onMouseEnter={() => setHover(value)}
                                    onFocus={() => setHover(value)}
                                    onClick={() => send(value)}
                                    aria-label={`Noter ${stars(value)} étoile${value > 2 ? "s" : ""}`}
                                    className={cn("absolute top-0 h-full w-1/2 focus-visible:outline-none", half === 0 ? "left-0" : "right-0")}
                                />
                            ))}
                        </span>
                    );
                })}
            </div>
            <span className="min-w-[7rem] text-[13px] tabular-nums text-muted-foreground" role="status">
                {rate.isPending || ratings.isLoading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : shown ? (
                    `${stars(shown)} ★ · ${LABELS[shown]}`
                ) : (
                    "Pas encore notée"
                )}
            </span>
        </div>
    );
}
