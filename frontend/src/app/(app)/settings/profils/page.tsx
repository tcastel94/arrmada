"use client";

/**
 * Paramètres → Profils famille (ADR-008).
 * ----------------------------------------------------------------
 * Les profils de l'écran « Qui regarde ? » de l'appli Android TV : chacun
 * a sa rangée Reprendre, ses épisodes vus, son « Pour toi » et ses demandes
 * « Pour ce soir ». Pas de code PIN ni de profil enfant (choix du 21/10/2026).
 * Le profil « Famille » est celui des TV sous Kodi et de la web app.
 */
import { useState, type FormEvent } from "react";
import { Loader2, Pencil, Plus, Trash2, Users } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Panel } from "@/components/shared/panel";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState } from "@/components/shared/empty-state";
import { TableSkeleton } from "@/components/shared/loading-skeleton";
import { FormField } from "@/components/settings/form-field";
import {
    MAX_PROFILES,
    PROFILE_COLORS,
    useCreateFamilyProfile,
    useDeleteFamilyProfile,
    useFamilyProfiles,
    useUpdateFamilyProfile,
    type FamilyProfile,
} from "@/hooks/use-family-profiles";
import { cn } from "@/lib/utils";

/** Avatar rond : emoji, sinon initiale, sur la couleur du profil (comme sur la TV). */
function Avatar({ profile, size = 44 }: { profile: Pick<FamilyProfile, "name" | "color" | "emoji">; size?: number }) {
    return (
        <span
            className="flex shrink-0 items-center justify-center rounded-full font-semibold text-[#0A0E16]"
            style={{ width: size, height: size, background: profile.color, fontSize: size * 0.42 }}
        >
            {profile.emoji || profile.name.trim().charAt(0).toUpperCase() || "?"}
        </span>
    );
}

/** Formulaire commun (ajout, modification) : nom, emoji, couleur. */
function ProfileForm({
    initial,
    submitLabel,
    pending,
    onSubmit,
}: {
    initial: { name: string; emoji: string; color: string };
    submitLabel: string;
    pending: boolean;
    onSubmit: (values: { name: string; emoji: string; color: string }) => void;
}) {
    const [name, setName] = useState(initial.name);
    const [emoji, setEmoji] = useState(initial.emoji);
    const [color, setColor] = useState(initial.color);
    const submit = (e: FormEvent) => {
        e.preventDefault();
        if (!name.trim()) return;
        onSubmit({ name: name.trim(), emoji: emoji.trim(), color });
    };
    return (
        <form onSubmit={submit} className="space-y-4">
            <div className="flex items-center gap-4">
                <Avatar profile={{ name: name || "?", emoji, color }} size={56} />
                <div className="grid flex-1 gap-3 sm:grid-cols-[1fr_120px]">
                    <FormField id="profile-name" label="Prénom">
                        <Input id="profile-name" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} placeholder="Thomas" autoFocus />
                    </FormField>
                    <FormField id="profile-emoji" label="Emoji (facultatif)">
                        <Input id="profile-emoji" value={emoji} maxLength={8} onChange={(e) => setEmoji(e.target.value)} placeholder="🎬" />
                    </FormField>
                </div>
            </div>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Couleur de l'avatar">
                {PROFILE_COLORS.map((c) => (
                    <button
                        key={c}
                        type="button"
                        role="radio"
                        aria-checked={c === color}
                        aria-label={`Couleur ${c}`}
                        onClick={() => setColor(c)}
                        className={cn(
                            "h-8 w-8 rounded-full ring-offset-2 ring-offset-background transition",
                            c === color ? "ring-2 ring-foreground" : "opacity-70 hover:opacity-100",
                        )}
                        style={{ background: c }}
                    />
                ))}
            </div>
            <div className="flex justify-end">
                <Button type="submit" disabled={pending || !name.trim()}>
                    {pending ? <Loader2 className="animate-spin" /> : null}
                    {submitLabel}
                </Button>
            </div>
        </form>
    );
}

export default function FamilyProfilesPage() {
    const { data: profiles, isLoading, isError, error, refetch } = useFamilyProfiles();
    const create = useCreateFamilyProfile();
    const update = useUpdateFamilyProfile();
    const del = useDeleteFamilyProfile();
    const [adding, setAdding] = useState(false);
    const [editing, setEditing] = useState<FamilyProfile | null>(null);
    const [deleting, setDeleting] = useState<FamilyProfile | null>(null);
    const full = (profiles?.length ?? 0) >= MAX_PROFILES;

    return (
        <div className="space-y-6">
            <Panel
                title="Profils famille"
                icon={Users}
                iconClassName="text-primary"
                action={
                    <Button size="sm" onClick={() => setAdding(true)} disabled={full || isLoading}>
                        <Plus />
                        Ajouter
                    </Button>
                }
                bodyClassName="space-y-4"
            >
                <p className="text-xs leading-relaxed text-muted-foreground">
                    Au lancement, l&apos;appli Android TV demande « Qui regarde ? ». Chaque profil a sa rangée Reprendre, ses épisodes vus,
                    son « Pour toi » (d&apos;après ce qu&apos;il regarde) et ses demandes « Pour ce soir » : l&apos;annonce « Prêt à
                    regarder » le suit sur n&apos;importe quelle TV. Les TV sous Kodi et cette web app restent sur le profil « Famille ».
                </p>
                {isLoading ? (
                    <TableSkeleton rows={3} />
                ) : isError ? (
                    <ErrorState error={error} onRetry={() => refetch()} />
                ) : (
                    <ul className="divide-y divide-white/[0.05]">
                        {profiles?.map((p) => (
                            <li key={p.id} className="flex items-center gap-3 py-3">
                                <Avatar profile={p} />
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm font-semibold">{p.name}</p>
                                    <p className="text-xs text-muted-foreground">
                                        {p.is_default ? "TV sous Kodi, web app, et quiconque ne choisit pas" : "Profil de l'appli TV"}
                                    </p>
                                </div>
                                <Button variant="ghost" size="sm" onClick={() => setEditing(p)} aria-label={`Modifier ${p.name}`}>
                                    <Pencil />
                                </Button>
                                {!p.is_default && (
                                    <Button variant="ghost" size="sm" onClick={() => setDeleting(p)} aria-label={`Supprimer ${p.name}`}>
                                        <Trash2 />
                                    </Button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
                {full && <p className="text-xs text-muted-foreground">{MAX_PROFILES} profils au plus.</p>}
            </Panel>

            <Dialog open={adding} onOpenChange={setAdding}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Nouveau profil</DialogTitle>
                        <DialogDescription>Il apparaît aussitôt dans « Qui regarde ? » sur les TV.</DialogDescription>
                    </DialogHeader>
                    <ProfileForm
                        initial={{ name: "", emoji: "", color: PROFILE_COLORS[(profiles?.length ?? 0) % PROFILE_COLORS.length] }}
                        submitLabel="Ajouter"
                        pending={create.isPending}
                        onSubmit={(values) =>
                            create.mutate(values, {
                                onSuccess: (p) => {
                                    toast.success(`Profil « ${p.name} » ajouté`);
                                    setAdding(false);
                                },
                                onError: (e) => toast.error("Ajout impossible", { description: e.message }),
                            })
                        }
                    />
                </DialogContent>
            </Dialog>

            <Dialog open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Modifier le profil</DialogTitle>
                        <DialogDescription>Nom, emoji et couleur de l&apos;avatar.</DialogDescription>
                    </DialogHeader>
                    {editing && (
                        <ProfileForm
                            key={editing.id}
                            initial={{ name: editing.name, emoji: editing.emoji, color: editing.color }}
                            submitLabel="Enregistrer"
                            pending={update.isPending}
                            onSubmit={(values) =>
                                update.mutate(
                                    { id: editing.id, ...values },
                                    {
                                        onSuccess: () => {
                                            toast.success("Profil enregistré");
                                            setEditing(null);
                                        },
                                        onError: (e) => toast.error("Enregistrement impossible", { description: e.message }),
                                    },
                                )
                            }
                        />
                    )}
                </DialogContent>
            </Dialog>

            <ConfirmDialog
                open={deleting !== null}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Supprimer « ${deleting?.name ?? ""} » ?`}
                description="Sa rangée Reprendre et ses épisodes vus sont effacés ; ses demandes en cours passent au profil « Famille »."
                destructive
                confirmLabel="Supprimer"
                onConfirm={() =>
                    deleting
                        ? del.mutateAsync(deleting.id).then(
                              () => {
                                  toast.success("Profil supprimé");
                                  setDeleting(null);
                              },
                              (e: Error) => toast.error("Suppression impossible", { description: e.message }),
                          )
                        : undefined
                }
            />
        </div>
    );
}
