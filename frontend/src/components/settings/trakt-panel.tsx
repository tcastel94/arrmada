"use client";

/**
 * Paramètres › Trakt : chaque profil famille relie SON compte Trakt (ADR-022).
 * ----------------------------------------------------------------
 * « Relier » affiche un code à taper sur trakt.tv/activate (depuis le
 * téléphone, par exemple) ; la page attend tant que le code n'a pas été tapé,
 * au rythme demandé par Trakt, puis passe le profil en « relié ».
 * Ensuite, sur la TV, ce profil reçoit une demande de note à la fin de chaque
 * film / épisode, et ce qu'il regarde part en direct dans son historique.
 */
import { useEffect, useRef, useState } from "react";
import { Check, Copy, ExternalLink, KeyRound, Link2, Loader2, Star, Unlink } from "lucide-react";
import { toast } from "sonner";
import { Panel } from "@/components/shared/panel";
import { Button } from "@/components/ui/button";
import {
    pollTraktLink,
    useRefreshTrakt,
    useTraktAccounts,
    useTraktStartLink,
    useTraktUnlink,
    type TraktCode,
    type TraktProfile,
} from "@/hooks/use-trakt";

const ENDED: Record<string, string> = {
    expired: "Code expiré : relance la liaison.",
    denied: "Accès refusé sur Trakt.",
    invalid: "Code inconnu de Trakt : relance la liaison.",
    used: "Code déjà utilisé : relance la liaison.",
    error: "Trakt ne répond pas : réessaie dans un instant.",
};

export function TraktPanel() {
    const { data, isLoading } = useTraktAccounts();
    return (
        <Panel title="Trakt" icon={Star} iconClassName="text-[#ED1C24]" className="h-full" bodyClassName="space-y-3 py-3">
            <p className="text-[13px] text-muted-foreground">
                Chaque profil relie son compte Trakt. Sur la TV, il note alors chaque film et épisode à la fin (5 étoiles, demi-étoiles),
                puis la saison et la série au dernier épisode ; ce qu&apos;il regarde part en direct dans son historique Trakt.
            </p>
            {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            ) : data && !data.configured ? (
                <NotConfigured />
            ) : (
                <ul className="divide-y divide-white/[0.05] rounded-xl bg-white/[0.03]">
                    {data?.profiles.map((profile) => <ProfileRow key={profile.profile_key} profile={profile} />)}
                </ul>
            )}
        </Panel>
    );
}

function NotConfigured() {
    const code = "rounded bg-white/[0.08] px-1 font-mono text-[12px] text-foreground";
    return (
        <div className="flex items-start gap-2 rounded-xl bg-warning/10 p-3 text-[13px] leading-snug text-muted-foreground">
            <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
            <ol className="list-decimal space-y-1 pl-4">
                <li>
                    Crée une application sur{" "}
                    <a href="https://trakt.tv/oauth/applications/new" target="_blank" rel="noreferrer noopener" className="text-primary hover:underline">
                        trakt.tv/oauth/applications/new
                    </a>{" "}
                    (nom : ArrMada ; redirect URI : <code className={code}>urn:ietf:wg:oauth:2.0:oob</code>).
                </li>
                <li>
                    Ajoute <code className={code}>TRAKT_CLIENT_ID=…</code> et <code className={code}>TRAKT_CLIENT_SECRET=…</code> dans le{" "}
                    <code className={code}>.env</code>, puis <code className={code}>docker compose up -d</code>.
                </li>
            </ol>
        </div>
    );
}

function ProfileRow({ profile }: { profile: TraktProfile }) {
    const start = useTraktStartLink();
    const unlink = useTraktUnlink();
    const refresh = useRefreshTrakt();
    const [code, setCode] = useState<TraktCode | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

    // Attente du code : on interroge au rythme demandé par Trakt, jusqu'à expiration
    useEffect(() => {
        if (!code) return;
        let delay = code.interval * 1000;
        const deadline = Date.now() + code.expires_in * 1000;
        let stopped = false;
        const tick = async () => {
            if (stopped) return;
            const result = await pollTraktLink(profile.profile_key, code.device_code).catch(() => ({ status: "pending" as const }));
            if (stopped) return;
            if (result.status === "linked") {
                toast.success(`Trakt relié : @${result.username || "?"} pour ${profile.name}`);
                setCode(null);
                refresh();
                return;
            }
            if (result.status !== "pending" || Date.now() > deadline) {
                toast.error("Liaison Trakt non faite", { description: ENDED[result.status] ?? ENDED.expired });
                setCode(null);
                return;
            }
            delay = Math.min(delay + 1000, 15_000); // Trakt demande de ralentir : on espace un peu
            timer.current = setTimeout(tick, delay);
        };
        timer.current = setTimeout(tick, delay);
        return () => {
            stopped = true;
            if (timer.current) clearTimeout(timer.current);
        };
    }, [code, profile.profile_key, profile.name, refresh]);

    const begin = () =>
        start.mutate(profile.profile_key, {
            onSuccess: setCode,
            onError: (e) => toast.error("Trakt injoignable", { description: e.message }),
        });

    return (
        <li className="space-y-2 px-3 py-2.5">
            <div className="flex items-center gap-3">
                <span
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[14px] font-semibold"
                    style={{ backgroundColor: `${profile.color}33`, color: profile.color }}
                    aria-hidden
                >
                    {profile.emoji || profile.name.slice(0, 1).toUpperCase()}
                </span>
                <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-semibold">{profile.name}</p>
                    <p className="truncate text-[12.5px] text-muted-foreground">
                        {profile.linked ? (
                            <span className="inline-flex items-center gap-1 text-success">
                                <Check className="h-3.5 w-3.5" /> @{profile.username || "compte relié"}
                            </span>
                        ) : (
                            "Pas de compte Trakt"
                        )}
                    </p>
                </div>
                {profile.linked ? (
                    <Button
                        size="sm"
                        variant="secondary"
                        onClick={() =>
                            unlink.mutate(profile.profile_key, {
                                onSuccess: () => toast.success(`Trakt délié pour ${profile.name}`),
                                onError: (e) => toast.error("Impossible de délier", { description: e.message }),
                            })
                        }
                        disabled={unlink.isPending}
                    >
                        <Unlink />
                        Délier
                    </Button>
                ) : code ? (
                    <Button size="sm" variant="secondary" onClick={() => setCode(null)}>
                        Annuler
                    </Button>
                ) : (
                    <Button size="sm" variant="tinted" onClick={begin} disabled={start.isPending}>
                        {start.isPending ? <Loader2 className="animate-spin" /> : <Link2 />}
                        Relier
                    </Button>
                )}
            </div>
            {code && <CodeBox code={code} />}
        </li>
    );
}

function CodeBox({ code }: { code: TraktCode }) {
    const copy = () => {
        navigator.clipboard?.writeText(code.user_code).then(
            () => toast.success("Code copié"),
            () => undefined,
        );
    };
    return (
        <div className="ml-11 space-y-1.5 rounded-xl bg-primary/[0.08] p-3 ring-1 ring-primary/30">
            <p className="text-[13px] text-muted-foreground">
                Ouvre{" "}
                <a href={code.verification_url} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-0.5 text-primary hover:underline">
                    {code.verification_url.replace(/^https?:\/\//, "")}
                    <ExternalLink className="h-3 w-3" />
                </a>{" "}
                (connecté au bon compte Trakt) et tape :
            </p>
            <div className="flex items-center gap-2">
                <span className="font-mono text-[22px] font-semibold tracking-[0.2em]" aria-label="Code Trakt">
                    {code.user_code}
                </span>
                <Button size="icon" variant="ghost" onClick={copy} aria-label="Copier le code">
                    <Copy />
                </Button>
            </div>
            <p className="flex items-center gap-1.5 text-[12px] text-muted-foreground" role="status">
                <Loader2 className="h-3.5 w-3.5 animate-spin" /> En attente de la validation sur Trakt…
            </p>
        </div>
    );
}
