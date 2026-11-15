"use client";

/**
 * Écran d'appoint du salon — la tablette posée sous la TV.
 * ----------------------------------------------------------------
 * Affiche, sans gêner le film, en grand (lu depuis le canapé, à 3-4 m) :
 *  - pendant une lecture : l'affiche sur toute la hauteur, l'heure de FIN
 *    prévue en très grand, l'heure de DÉBUT, le temps restant, la barre de
 *    progression, le titre, l'heure et le volume de l'ampli ; avec l'appli
 *    Android en plus : formats (4K, Dolby Vision, Atmos), pistes, chapitre,
 *    générique et épisode suivant, fiche (résumé, distribution) et une
 *    TÉLÉCOMMANDE TACTILE (pause, −10 s / +30 s, passer l'intro, pistes) ;
 *  - au repos : une grande horloge, « Ce soir » (reprendre, Ma liste,
 *    nouveaux films : un toucher → confirmation → lancé sur la TV de la
 *    pièce), les sorties de ce soir / demain, les téléchargements en cours
 *    et l'ampli de la pièce.
 *
 * Trois états, comme une petite machine à états :
 *  1. « appairage » : pas encore de jeton → code + QR code à valider depuis
 *     le téléphone (Réglages → Kodi → Appareils), comme pour une TV ;
 *  2. « affichage » : jeton « écran » (GET /api/ambient, relevé toutes les
 *     10 s, 5 s pendant une lecture ; et POST /api/ambient/command pour la
 *     télécommande de la lecture en cours de sa pièce) ;
 *  3. « aperçu » : depuis un PC où l'on est connecté en admin, pour régler
 *     l'affichage sans appairer (bouton sur l'écran d'appairage).
 *
 * Luminosité (« mode séance ») : pendant une lecture, la page s'assombrit
 * et, dans Fully Kiosk, baisse le rétroéclairage (`?seance=6`, 0-255) ; au
 * repos elle remonte (`?repos=40`). Toucher l'écran rallume 20 s.
 *
 * Pourquoi pas de réglage dans Kodi : la lecture en cours vient du suivi
 * que l'add-on envoie déjà au serveur (aucun serveur web Kodi à ouvrir).
 */
import { useCallback, useEffect, useState } from "react";
import { getToken } from "@/lib/api-client";
import { getScreenToken, readOptions, setScreenToken, type ScreenOptions } from "@/lib/ambient";
import type { Auth } from "./_lib/api";
import { PairingView } from "./_components/pairing-view";
import { AmbientView } from "./_components/ambient-view";

/*
 * Organisation des fichiers (cette page ne fait qu'assembler) :
 *  - _lib/api.ts        : échanges avec le serveur, délais de relevé ;
 *  - _lib/hooks.ts      : horloge, rétroéclairage, écran allumé, anti-marquage ;
 *  - _lib/units.ts      : l'unité d'écran « u » ;
 *  - _components/…      : un fichier par morceau d'écran (appairage,
 *    affichage, séance, télécommande, repos, « Ce soir », panneaux, fiches).
 * Les dossiers commençant par « _ » ne deviennent pas des pages (Next.js).
 */

/* ══════════════════════════════════════════════════════════════
   Page
   ══════════════════════════════════════════════════════════════ */

export default function EcranPage() {
    // Lu après le premier rendu : localStorage et l'adresse n'existent que
    // dans le navigateur (le serveur Next.js prépare la page sans eux).
    const [auth, setAuth] = useState<Auth | null | undefined>(undefined);
    const [options, setOptions] = useState<ScreenOptions>({ dim: 6, rest: 40, room: "salon" });
    const [adminAvailable, setAdminAvailable] = useState(false);

    useEffect(() => {
        setOptions(readOptions(window.location.search));
        const token = getScreenToken();
        setAuth(token ? { kind: "screen", token } : null);
        setAdminAvailable(!!getToken());
    }, []);

    const onPaired = useCallback((token: string) => {
        setScreenToken(token);
        setAuth({ kind: "screen", token });
    }, []);

    const onRevoked = useCallback(() => {
        setScreenToken(null);
        setAuth(null);
    }, []);

    return (
        // Défilement vertical possible (téléphone, tablette en portrait) ; en
        // paysage sur la tablette, tout tient sur un écran.
        <main className="fixed inset-0 overflow-y-auto overflow-x-hidden bg-black text-slate-200 selection:bg-transparent">
            {auth === undefined ? null : auth === null ? (
                <PairingView
                    onPaired={onPaired}
                    onPreview={
                        adminAvailable
                            ? () => {
                                  const token = getToken();
                                  if (token) setAuth({ kind: "admin", token });
                              }
                            : undefined
                    }
                />
            ) : (
                <AmbientView auth={auth} options={options} onRevoked={onRevoked} onLeavePreview={() => setAuth(null)} />
            )}
        </main>
    );
}
