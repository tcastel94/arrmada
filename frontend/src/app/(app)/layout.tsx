"use client";

import { Sidebar } from "@/components/layout/sidebar";
import { MobileNav } from "@/components/layout/mobile-nav";
import { CommandPalette } from "@/components/layout/command-palette";
import { useEffect, useState } from "react";
import { isAuthenticated } from "@/lib/api-client";
import { useRouter } from "next/navigation";
import { useSetupStatus } from "@/hooks/use-setup";
import { Loader2 } from "lucide-react";

export default function AppLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const router = useRouter();
    const [ready, setReady] = useState(false);
    const { data: setupStatus, isLoading: setupLoading, isError } = useSetupStatus();

    useEffect(() => {
        if (setupLoading) return;

        // If setup status check failed OR app is not configured → redirect to wizard
        if (isError || (setupStatus && !setupStatus.is_configured)) {
            router.replace("/setup");
            return;
        }

        // If not authenticated, redirect to login
        if (!isAuthenticated()) {
            router.replace("/login");
        } else {
            setReady(true);
        }
    }, [router, setupStatus, setupLoading, isError]);

    if (setupLoading || !ready) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="min-h-screen">
            <Sidebar />
            <MobileNav />
            <CommandPalette />
            <main className="lg:pl-[260px] pb-16 lg:pb-0">{children}</main>
        </div>
    );
}
