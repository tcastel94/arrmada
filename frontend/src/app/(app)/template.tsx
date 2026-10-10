"use client";

/**
 * Transition d'entrée de chaque page.
 * Un `template` Next.js est re-monté à chaque navigation (contrairement au
 * `layout`), ce qui permet de rejouer l'animation à chaque changement de page.
 */
import { motion } from "framer-motion";
import { EASE_OUT } from "@/lib/motion";

export default function Template({ children }: { children: React.ReactNode }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 14, filter: "blur(6px)" }}
            // transitionEnd : on retire le filtre à la fin, sinon il « piège » les
            // éléments position:fixed des pages (barres flottantes…).
            animate={{ opacity: 1, y: 0, filter: "blur(0px)", transitionEnd: { filter: "none", transform: "none" } }}
            transition={{ duration: 0.5, ease: EASE_OUT }}
        >
            {children}
        </motion.div>
    );
}
