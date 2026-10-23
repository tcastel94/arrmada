"use client";

/**
 * Choix de la liste affichée : « Famille », « Tom »… (pastilles iOS).
 * Masqué quand la maison n'a que le profil « Famille ».
 */
import { useFamilyProfiles } from "@/hooks/use-family-profiles";
import { useWatchlistProfile } from "@/hooks/use-watchlist";

export function WatchlistProfilePicker({ className }: { className?: string }) {
    const { data: profiles } = useFamilyProfiles();
    const [profile, setProfile] = useWatchlistProfile();
    if (!profiles || profiles.length < 2) return null;
    return (
        <div className={className}>
            <div className="scrollbar-none -mx-4 flex gap-2 overflow-x-auto px-4 md:mx-0 md:px-0" role="radiogroup" aria-label="Liste de">
                {profiles.map((p) => {
                    const id = p.is_default ? null : p.id;
                    const active = profile === id;
                    return (
                        <button
                            key={p.id}
                            type="button"
                            role="radio"
                            aria-checked={active}
                            data-active={active}
                            onClick={() => setProfile(id)}
                            className="chip shrink-0"
                        >
                            <span
                                aria-hidden
                                className="flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-semibold text-white"
                                // Profil sans couleur choisie : gris système plutôt qu'une pastille invisible
                                style={{ background: p.color || "#636366" }}
                            >
                                {p.emoji || p.name.charAt(0).toUpperCase()}
                            </span>
                            {p.name}
                        </button>
                    );
                })}
            </div>
        </div>
    );
}
