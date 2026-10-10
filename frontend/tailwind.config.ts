import type { Config } from "tailwindcss";

/**
 * Tailwind — branché sur les variables CSS de globals.css.
 * Les couleurs sont exprimées en HSL avec support de l'opacité
 * (ex: bg-primary/20) grâce au placeholder <alpha-value>.
 */
const hsl = (v: string) => `hsl(var(${v}) / <alpha-value>)`;

const config: Config = {
    darkMode: ["class"],
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: ["var(--font-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
                mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
            },
            colors: {
                background: hsl("--background"),
                foreground: hsl("--foreground"),
                card: {
                    DEFAULT: hsl("--card"),
                    foreground: hsl("--card-foreground"),
                },
                popover: {
                    DEFAULT: hsl("--popover"),
                    foreground: hsl("--popover-foreground"),
                },
                primary: {
                    DEFAULT: hsl("--primary"),
                    foreground: hsl("--primary-foreground"),
                },
                brand: {
                    DEFAULT: hsl("--brand"),
                    foreground: hsl("--brand-foreground"),
                },
                secondary: {
                    DEFAULT: hsl("--secondary"),
                    foreground: hsl("--secondary-foreground"),
                },
                muted: {
                    DEFAULT: hsl("--muted"),
                    foreground: hsl("--muted-foreground"),
                },
                accent: {
                    DEFAULT: hsl("--accent"),
                    foreground: hsl("--accent-foreground"),
                },
                destructive: {
                    DEFAULT: hsl("--destructive"),
                    foreground: hsl("--destructive-foreground"),
                },
                success: {
                    DEFAULT: hsl("--success"),
                    foreground: hsl("--success-foreground"),
                },
                warning: {
                    DEFAULT: hsl("--warning"),
                    foreground: hsl("--warning-foreground"),
                },
                border: hsl("--border"),
                input: hsl("--input"),
                ring: hsl("--ring"),
                chart: {
                    "1": hsl("--chart-1"),
                    "2": hsl("--chart-2"),
                    "3": hsl("--chart-3"),
                    "4": hsl("--chart-4"),
                    "5": hsl("--chart-5"),
                },
            },
            borderRadius: {
                xl: "calc(var(--radius) + 4px)",
                lg: "var(--radius)",
                md: "calc(var(--radius) - 4px)",
                sm: "calc(var(--radius) - 6px)",
            },
            transitionTimingFunction: {
                // Courbe « out-expo » douce : utilisée pour tous les mouvements UI.
                smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
                spring: "cubic-bezier(0.34, 1.56, 0.64, 1)",
            },
            keyframes: {
                // Nappes de lumière du fond (aurora) — uniquement transform pour rester fluide.
                "aurora-1": {
                    "0%, 100%": { transform: "translate3d(0,0,0) scale(1)" },
                    "33%": { transform: "translate3d(8%, -6%, 0) scale(1.12)" },
                    "66%": { transform: "translate3d(-6%, 5%, 0) scale(0.95)" },
                },
                "aurora-2": {
                    "0%, 100%": { transform: "translate3d(0,0,0) scale(1.05)" },
                    "50%": { transform: "translate3d(-10%, 8%, 0) scale(0.9)" },
                },
                "aurora-3": {
                    "0%, 100%": { transform: "translate3d(0,0,0) rotate(0deg)" },
                    "50%": { transform: "translate3d(6%, 10%, 0) rotate(25deg)" },
                },
                float: {
                    "0%, 100%": { transform: "translateY(0)" },
                    "50%": { transform: "translateY(-8px)" },
                },
                "pulse-ring": {
                    "0%": { transform: "scale(1)", opacity: "0.7" },
                    "100%": { transform: "scale(2.6)", opacity: "0" },
                },
                "pulse-glow": {
                    "0%, 100%": { opacity: "0.55", filter: "brightness(1)" },
                    "50%": { opacity: "1", filter: "brightness(1.25)" },
                },
                "gradient-x": {
                    "0%, 100%": { backgroundPosition: "0% 50%" },
                    "50%": { backgroundPosition: "100% 50%" },
                },
                shimmer: {
                    "100%": { transform: "translateX(100%)" },
                },
                "progress-stripes": {
                    "0%": { backgroundPosition: "0 0" },
                    "100%": { backgroundPosition: "28px 0" },
                },
                shake: {
                    "0%, 100%": { transform: "translateX(0)" },
                    "20%, 60%": { transform: "translateX(-8px)" },
                    "40%, 80%": { transform: "translateX(8px)" },
                },
                "spin-slow": {
                    to: { transform: "rotate(360deg)" },
                },
                marquee: {
                    from: { transform: "translateX(0)" },
                    to: { transform: "translateX(-50%)" },
                },
                "accordion-down": {
                    from: { height: "0" },
                    to: { height: "var(--radix-accordion-content-height)" },
                },
                "accordion-up": {
                    from: { height: "var(--radix-accordion-content-height)" },
                    to: { height: "0" },
                },
            },
            animation: {
                "aurora-1": "aurora-1 26s ease-in-out infinite",
                "aurora-2": "aurora-2 32s ease-in-out infinite",
                "aurora-3": "aurora-3 40s ease-in-out infinite",
                float: "float 6s ease-in-out infinite",
                "pulse-ring": "pulse-ring 2s cubic-bezier(0.22, 1, 0.36, 1) infinite",
                "pulse-glow": "pulse-glow 3s ease-in-out infinite",
                "gradient-x": "gradient-x 8s ease infinite",
                shimmer: "shimmer 1.6s infinite",
                "progress-stripes": "progress-stripes 1s linear infinite",
                shake: "shake 0.45s cubic-bezier(0.36, 0.07, 0.19, 0.97)",
                "spin-slow": "spin-slow 12s linear infinite",
                marquee: "marquee 40s linear infinite",
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
            },
            backgroundImage: {
                "brand-gradient":
                    "linear-gradient(110deg, hsl(var(--primary)), hsl(var(--brand)))",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
export default config;
