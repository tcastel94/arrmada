"use client";

/**
 * Transition entre deux pages.
 * ----------------------------------------------------------------
 * Next.js recrée ce « template » à chaque changement d'URL (contrairement
 * au layout, qui reste en place) : c'est l'endroit idéal pour un court
 * fondu d'entrée, qui évite l'effet « page qui clignote » au changement.
 *
 * Seule l'opacité est animée, volontairement : un déplacement (transform)
 * sur ce conteneur casserait les éléments « fixed » des pages (barres
 * d'actions flottantes, lecteur) pendant l'animation.
 */
import { motion } from "framer-motion";

export default function AppTemplate({ children }: { children: React.ReactNode }) {
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.22, ease: [0.25, 1, 0.5, 1] }}>
            {children}
        </motion.div>
    );
}
