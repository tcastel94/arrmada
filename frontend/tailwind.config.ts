import type { Config } from "tailwindcss";

/**
 * Tailwind — branché sur les variables CSS de globals.css.
 * Les couleurs sont exprimées en HSL avec support de l'opacité
 * (ex: bg-primary/20) grâce au placeholder <alpha-value>.
 *
 * Refonte « Épuré » : police système Apple en priorité (SF Pro sur
 * iPhone / Mac, ce qui donne le rendu d'une app native), Geist ailleurs.
 * Les animations décoratives de l'ancien thème (aurora, halos pulsés,
 * dégradés animés) sont gardées sous leur nom mais rendues immobiles,
 * pour qu'aucune page ne casse avant d'être redessinée.
 */
const hsl = (v: string) => `hsl(var(${v}) / <alpha-value>)`;

const STILL = { "0%, 100%": { transform: "none", opacity: "1" } };

const config: Config = {
    darkMode: ["class"],
    content: [
        "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
        // lib/nav.ts porte les couleurs des vignettes du menu (classes à générer)
        "./src/lib/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            fontFamily: {
                sans: [
                    "-apple-system",
                    "BlinkMacSystemFont",
                    "var(--font-sans)",
                    "ui-sans-serif",
                    "system-ui",
                    "sans-serif",
                ],
                mono: ["ui-monospace", "SFMono-Regular", "var(--font-mono)", "monospace"],
            },
            fontSize: {
                // Échelle typographique iOS (tailles « Dynamic Type » par défaut).
                "ios-large": ["2.125rem", { lineHeight: "2.5rem", letterSpacing: "-0.025em", fontWeight: "700" }],
                "ios-title": ["1.375rem", { lineHeight: "1.75rem", letterSpacing: "-0.02em", fontWeight: "700" }],
                "ios-headline": ["1.0625rem", { lineHeight: "1.375rem", letterSpacing: "-0.01em", fontWeight: "600" }],
                "ios-body": ["1.0625rem", { lineHeight: "1.375rem", letterSpacing: "-0.01em" }],
                "ios-footnote": ["0.8125rem", { lineHeight: "1.125rem" }],
                "ios-caption": ["0.75rem", { lineHeight: "1rem" }],
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
                // Courbe douce façon iOS : utilisée pour tous les mouvements UI.
                smooth: "cubic-bezier(0.25, 1, 0.5, 1)",
                // Ancien nom gardé : plus de rebond exagéré.
                spring: "cubic-bezier(0.25, 1, 0.5, 1)",
            },
            keyframes: {
                // Effets de l'ancien thème, immobilisés (voir en-tête).
                "aurora-1": STILL,
                "aurora-2": STILL,
                "aurora-3": STILL,
                float: STILL,
                "pulse-glow": STILL,
                "gradient-x": STILL,
                "pulse-ring": {
                    "0%": { transform: "scale(1)", opacity: "0.6" },
                    "100%": { transform: "scale(2.2)", opacity: "0" },
                },
                shimmer: {
                    "0%, 100%": { opacity: "1" },
                    "50%": { opacity: "0.55" },
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
                "aurora-1": "aurora-1 1s linear",
                "aurora-2": "aurora-2 1s linear",
                "aurora-3": "aurora-3 1s linear",
                float: "float 1s linear",
                "pulse-ring": "pulse-ring 2s cubic-bezier(0.25, 1, 0.5, 1) infinite",
                "pulse-glow": "pulse-glow 1s linear",
                "gradient-x": "gradient-x 1s linear",
                shimmer: "shimmer 1.6s ease-in-out infinite",
                "progress-stripes": "progress-stripes 1s linear infinite",
                shake: "shake 0.45s cubic-bezier(0.36, 0.07, 0.19, 0.97)",
                "spin-slow": "spin-slow 12s linear infinite",
                marquee: "marquee 40s linear infinite",
                "accordion-down": "accordion-down 0.2s ease-out",
                "accordion-up": "accordion-up 0.2s ease-out",
            },
            backgroundImage: {
                // Ancien dégradé de marque : désormais un aplat d'accent.
                "brand-gradient": "linear-gradient(hsl(var(--primary)), hsl(var(--primary)))",
            },
        },
    },
    plugins: [require("tailwindcss-animate")],
};
export default config;
