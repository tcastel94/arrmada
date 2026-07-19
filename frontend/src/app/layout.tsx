import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: {
    default: "ArrMada",
    template: "%s — ArrMada",
  },
  description: "Unified *arr stack management dashboard",
  applicationName: "ArrMada",
  // Icônes servies par convention App Router : src/app/{icon,apple-icon}.png + favicon.ico
  openGraph: {
    title: "ArrMada — Unified Media Dashboard",
    description: "Unified *arr stack management dashboard",
    siteName: "ArrMada",
    type: "website",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "ArrMada" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "ArrMada — Unified Media Dashboard",
    description: "Unified *arr stack management dashboard",
    images: ["/og-image.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
