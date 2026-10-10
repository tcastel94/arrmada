import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { Providers } from "@/components/providers";

// Polices embarquées (pas d'appel Google Fonts au build → build Docker
// reproductible même sans accès réseau).
const geistSans = localFont({
    src: "./fonts/GeistVF.woff",
    variable: "--font-sans",
    weight: "100 900",
    display: "swap",
});
const geistMono = localFont({
    src: "./fonts/GeistMonoVF.woff",
    variable: "--font-mono",
    weight: "100 900",
    display: "swap",
});

export const metadata: Metadata = {
    title: {
        default: "ArrMada",
        template: "%s — ArrMada",
    },
    description: "Le poste de commandement unifié de ta stack *arr",
    applicationName: "ArrMada",
    // Icônes servies par convention App Router : src/app/{icon,apple-icon}.png + favicon.ico
    openGraph: {
        title: "ArrMada — Unified Media Dashboard",
        description: "Le poste de commandement unifié de ta stack *arr",
        siteName: "ArrMada",
        type: "website",
        images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "ArrMada" }],
    },
    twitter: {
        card: "summary_large_image",
        title: "ArrMada — Unified Media Dashboard",
        description: "Le poste de commandement unifié de ta stack *arr",
        images: ["/og-image.png"],
    },
    appleWebApp: {
        capable: true,
        title: "ArrMada",
        statusBarStyle: "black-translucent",
    },
};

export const viewport: Viewport = {
    themeColor: "#05080f",
    colorScheme: "dark",
    width: "device-width",
    initialScale: 1,
    viewportFit: "cover",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="fr" className="dark" suppressHydrationWarning>
            <body className={`${geistSans.variable} ${geistMono.variable} font-sans antialiased`}>
                <Providers>{children}</Providers>
            </body>
        </html>
    );
}
