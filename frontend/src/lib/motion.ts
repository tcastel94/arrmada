/**
 * Presets d'animation framer-motion partagés.
 * ----------------------------------------------------------------
 * Pourquoi un fichier dédié : chaque page définissait ses propres
 * "container"/"fadeUp" avec des durées différentes → rendu incohérent.
 * Ici, une seule courbe (out-expo) et des durées calibrées.
 *
 * Usage typique :
 *   <motion.div variants={stagger()} initial="hidden" animate="show">
 *     <motion.div variants={fadeUp}>…</motion.div>
 *   </motion.div>
 */
import type { Transition, Variants } from "framer-motion";

/** Courbe « out-expo » : départ vif, arrivée très douce. */
export const EASE_OUT: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** Ressort réactif pour les éléments interactifs (pills, toggles). */
export const SPRING: Transition = { type: "spring", stiffness: 420, damping: 34, mass: 0.8 };

/** Ressort plus souple pour les gros blocs (cartes, panneaux). */
export const SPRING_SOFT: Transition = { type: "spring", stiffness: 220, damping: 28 };

/** Conteneur qui déclenche ses enfants en cascade. */
export function stagger(delayChildren = 0, staggerChildren = 0.06): Variants {
    return {
        hidden: {},
        show: { transition: { delayChildren, staggerChildren } },
    };
}

/** Apparition par le bas avec léger flou (effet « mise au point »). */
export const fadeUp: Variants = {
    hidden: { opacity: 0, y: 18, filter: "blur(6px)" },
    show: {
        opacity: 1,
        y: 0,
        filter: "blur(0px)",
        transition: { duration: 0.55, ease: EASE_OUT },
        // Retire le filtre une fois l'animation finie (un filter, même nul,
        // crée un contexte d'empilement qui gêne les éléments fixed/sticky).
        transitionEnd: { filter: "none" },
    },
};

/** Apparition simple en fondu. */
export const fadeIn: Variants = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { duration: 0.4, ease: EASE_OUT } },
};

/** Zoom léger — pour les posters et tuiles. */
export const scaleIn: Variants = {
    hidden: { opacity: 0, scale: 0.92, y: 10 },
    show: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: { duration: 0.45, ease: EASE_OUT },
    },
};

/** Entrée latérale — pour les listes / timelines. */
export const slideIn: Variants = {
    hidden: { opacity: 0, x: -14 },
    show: { opacity: 1, x: 0, transition: { duration: 0.4, ease: EASE_OUT } },
};
