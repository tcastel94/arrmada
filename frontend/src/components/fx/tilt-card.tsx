"use client";

/**
 * Inclinaison 3D au survol (effet « carte holographique »), avec reflet
 * qui suit le pointeur. Désactivé sur écran tactile (pas de survol).
 */
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useRef, type ReactNode, type PointerEvent } from "react";
import { cn } from "@/lib/utils";

interface TiltCardProps {
    children: ReactNode;
    className?: string;
    /** Angle max en degrés. */
    max?: number;
    /** Reflet lumineux. */
    glare?: boolean;
}

export function TiltCard({ children, className, max = 9, glare = true }: TiltCardProps) {
    const ref = useRef<HTMLDivElement>(null);
    const px = useMotionValue(0.5);
    const py = useMotionValue(0.5);
    const cfg = { stiffness: 260, damping: 22 };
    const rotateX = useSpring(useTransform(py, [0, 1], [max, -max]), cfg);
    const rotateY = useSpring(useTransform(px, [0, 1], [-max, max]), cfg);
    const glareX = useTransform(px, [0, 1], ["0%", "100%"]);
    const glareY = useTransform(py, [0, 1], ["0%", "100%"]);
    const glareBg = useTransform(
        [glareX, glareY] as never,
        ([x, y]: string[]) =>
            `radial-gradient(circle at ${x} ${y}, rgba(255,255,255,0.22), transparent 55%)`,
    );

    const onMove = (e: PointerEvent<HTMLDivElement>) => {
        if (e.pointerType !== "mouse" || !ref.current) return;
        const r = ref.current.getBoundingClientRect();
        px.set((e.clientX - r.left) / r.width);
        py.set((e.clientY - r.top) / r.height);
    };
    const onLeave = () => {
        px.set(0.5);
        py.set(0.5);
    };

    return (
        <div className="perspective">
            <motion.div
                ref={ref}
                onPointerMove={onMove}
                onPointerLeave={onLeave}
                style={{ rotateX, rotateY, transformStyle: "preserve-3d" }}
                className={cn("group relative will-change-transform", className)}
            >
                {children}
                {glare && (
                    <motion.div
                        aria-hidden
                        className="pointer-events-none absolute inset-0 z-10 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
                        style={{ background: glareBg }}
                    />
                )}
            </motion.div>
        </div>
    );
}
