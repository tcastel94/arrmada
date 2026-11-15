"use client";

// Rôle : écran d'appairage (code + QR code) tant que la tablette n'a pas de jeton.

import { useEffect, useState } from "react";
import { Loader2, WifiOff } from "lucide-react";
import { BrandIcon } from "@/components/brand/brand-mark";
import { API_URL } from "@/lib/constants";
import { platformName } from "@/lib/ambient";
import { HttpError } from "../_lib/api";

/* ══════════════════════════════════════════════════════════════
   1. Appairage
   ══════════════════════════════════════════════════════════════ */

interface PairStart {
    device_code: string;
    user_code: string;
    verification_url: string;
    qr_url: string;
    expires_in: number;
    interval: number;
}

export function PairingView({ onPaired, onPreview }: { onPaired: (token: string) => void; onPreview?: () => void }) {
    const [pairing, setPairing] = useState<PairStart | null>(null);
    const [error, setError] = useState("");
    const [attempt, setAttempt] = useState(0);

    // Demande un code (et en redemande un s'il expire ou si le serveur est absent).
    useEffect(() => {
        let cancelled = false;
        let retry: ReturnType<typeof setTimeout> | undefined;
        (async () => {
            try {
                const response = await fetch(`${API_URL}/api/devices/pair/start`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ platform: platformName(navigator.userAgent), kind: "screen" }),
                });
                if (response.status === 403) {
                    throw new HttpError(403, "Appairage possible seulement depuis le réseau local.");
                }
                if (!response.ok) throw new HttpError(response.status, `Le serveur répond ${response.status}.`);
                const data: PairStart = await response.json();
                if (!cancelled) {
                    setPairing(data);
                    setError("");
                }
            } catch (e) {
                if (cancelled) return;
                setPairing(null);
                setError(e instanceof HttpError ? e.message : "Serveur ArrMada injoignable.");
                retry = setTimeout(() => setAttempt((n) => n + 1), 15_000);
            }
        })();
        return () => {
            cancelled = true;
            if (retry) clearTimeout(retry);
        };
    }, [attempt]);

    // « Est-ce validé ? » toutes les `interval` secondes.
    useEffect(() => {
        if (!pairing) return;
        let stopped = false;
        const timer = setInterval(async () => {
            try {
                const response = await fetch(`${API_URL}/api/devices/pair/poll`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ device_code: pairing.device_code }),
                });
                if (response.status === 410) {
                    // Code expiré (10 min) : on en demande un nouveau
                    if (!stopped) setAttempt((n) => n + 1);
                    return;
                }
                if (!response.ok) return;
                const data = await response.json();
                if (data.status === "ok" && data.token && !stopped) onPaired(data.token);
            } catch {
                // réseau coupé un instant : on réessaie au tour suivant
            }
        }, Math.max(2, pairing.interval) * 1000);
        return () => {
            stopped = true;
            clearInterval(timer);
        };
    }, [pairing, onPaired]);

    return (
        <div className="flex min-h-full items-center justify-center p-8">
            <div className="flex w-full max-w-4xl flex-col items-center gap-10 md:flex-row md:items-center md:gap-14">
                <div className="shrink-0">
                    {pairing ? (
                        // QR code fabriqué par le serveur : il pointe vers la page d'appairage de la web app
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={`${API_URL}${pairing.qr_url}`}
                            alt="QR code d'appairage"
                            className="h-56 w-56 rounded-2xl bg-white p-3 opacity-90"
                        />
                    ) : (
                        <div className="grid h-56 w-56 place-items-center rounded-2xl border border-white/10 bg-white/[0.03]">
                            {error ? <WifiOff className="h-10 w-10 text-slate-500" /> : <Loader2 className="h-8 w-8 animate-spin text-slate-500" />}
                        </div>
                    )}
                </div>
                <div className="min-w-0 flex-1 space-y-5 text-center md:text-left">
                    <div className="flex items-center justify-center gap-3 md:justify-start">
                        <div className="h-9 w-9 overflow-hidden rounded-xl">
                            <BrandIcon />
                        </div>
                        <p className="text-sm uppercase tracking-[0.25em] text-slate-400">Écran d&apos;appoint</p>
                    </div>
                    <h1 className="text-3xl font-semibold text-slate-100">Appairer cet écran</h1>
                    {pairing ? (
                        <>
                            <div className="flex justify-center gap-2 md:justify-start" aria-label={`Code ${pairing.user_code}`}>
                                {pairing.user_code.split("").map((char, i) => (
                                    <span
                                        key={i}
                                        className="grid h-16 w-12 place-items-center rounded-xl border border-[#4A9EFF]/40 bg-[#4A9EFF]/10 font-mono text-3xl font-semibold text-[#8CC4FF]"
                                    >
                                        {char}
                                    </span>
                                ))}
                            </div>
                            <p className="text-base leading-relaxed text-slate-400">
                                Vise le QR code avec ton téléphone connecté à ArrMada, ou va dans{" "}
                                <span className="text-slate-200">Réglages → Kodi → Appareils → Appairer</span> et saisis ce code.
                                Choisis la pièce de cet écran : il affichera ce qui passe sur la TV de cette pièce.
                            </p>
                            <p className="flex items-center justify-center gap-2 text-sm text-slate-500 md:justify-start">
                                <Loader2 className="h-4 w-4 animate-spin" /> En attente de validation…
                            </p>
                        </>
                    ) : error ? (
                        <p className="text-base text-amber-300/90">
                            {error} <span className="text-slate-500">Nouvel essai dans quelques secondes.</span>
                        </p>
                    ) : (
                        <p className="text-base text-slate-500">Demande d&apos;un code…</p>
                    )}
                    {onPreview && (
                        <button
                            type="button"
                            onClick={onPreview}
                            className="rounded-lg border border-white/10 px-3 py-1.5 text-sm text-slate-400 transition hover:border-[#4A9EFF]/50 hover:text-slate-200"
                        >
                            Aperçu avec ma session admin (sans appairer)
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
}
