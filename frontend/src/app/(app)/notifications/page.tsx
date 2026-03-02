"use client";

import { Header } from "@/components/layout/header";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/empty-state";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import {
    Bell,
    CheckCheck,
    AlertTriangle,
    AlertCircle,
    CheckCircle2,
    Info,
    Server,
} from "lucide-react";
import {
    useNotifications,
    useMarkRead,
    useMarkAllRead,
} from "@/hooks/use-notifications";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";

const SEVERITY_CONFIG: Record<
    string,
    { icon: typeof Info; color: string; bg: string }
> = {
    info: { icon: Info, color: "text-blue-400", bg: "bg-blue-500/10" },
    success: {
        icon: CheckCircle2,
        color: "text-emerald-400",
        bg: "bg-emerald-500/10",
    },
    warning: {
        icon: AlertTriangle,
        color: "text-yellow-400",
        bg: "bg-yellow-500/10",
    },
    error: {
        icon: AlertCircle,
        color: "text-red-400",
        bg: "bg-red-500/10",
    },
};

function timeAgo(dateStr: string): string {
    const now = new Date();
    const date = new Date(dateStr);
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return "À l'instant";
    if (seconds < 3600) return `Il y a ${Math.floor(seconds / 60)}min`;
    if (seconds < 86400) return `Il y a ${Math.floor(seconds / 3600)}h`;
    return `Il y a ${Math.floor(seconds / 86400)}j`;
}

export default function NotificationsPage() {
    const { data, isLoading } = useNotifications(100);
    const markRead = useMarkRead();
    const markAllRead = useMarkAllRead();

    if (isLoading) {
        return (
            <>
                <Header title="Notifications" />
                <div className="p-6">
                    <PageSkeleton />
                </div>
            </>
        );
    }

    const notifications = data?.items ?? [];
    const unreadCount = data?.unread_count ?? 0;

    return (
        <>
            <Header title="Notifications" />
            <div className="p-6 max-w-3xl mx-auto space-y-4">
                {/* Header bar */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Bell className="h-5 w-5 text-muted-foreground" />
                        <span className="text-sm text-muted-foreground">
                            {unreadCount > 0
                                ? `${unreadCount} non lue${unreadCount > 1 ? "s" : ""}`
                                : "Tout est lu"}
                        </span>
                    </div>
                    {unreadCount > 0 && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => markAllRead.mutate()}
                            className="text-xs gap-1.5"
                        >
                            <CheckCheck className="h-3.5 w-3.5" />
                            Tout marquer comme lu
                        </Button>
                    )}
                </div>

                {/* List */}
                {notifications.length === 0 ? (
                    <EmptyState
                        icon={Bell}
                        title="Aucune notification"
                        description="Les alertes de services, syncs TRaSH et autres événements apparaîtront ici"
                    />
                ) : (
                    <div className="space-y-2">
                        {notifications.map((notif, i) => {
                            const config =
                                SEVERITY_CONFIG[notif.severity] ??
                                SEVERITY_CONFIG.info;
                            const Icon = config.icon;

                            return (
                                <motion.div
                                    key={notif.id}
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.03 }}
                                >
                                    <Card
                                        className={cn(
                                            "cursor-pointer transition-all hover:bg-muted/50",
                                            !notif.is_read &&
                                            "border-l-2 border-l-primary"
                                        )}
                                        onClick={() => {
                                            if (!notif.is_read)
                                                markRead.mutate(notif.id);
                                        }}
                                    >
                                        <CardContent className="flex items-start gap-3 p-4">
                                            <div
                                                className={cn(
                                                    "rounded-full p-2 shrink-0",
                                                    config.bg
                                                )}
                                            >
                                                <Icon
                                                    className={cn(
                                                        "h-4 w-4",
                                                        config.color
                                                    )}
                                                />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p
                                                        className={cn(
                                                            "text-sm",
                                                            !notif.is_read
                                                                ? "font-semibold"
                                                                : "font-medium text-muted-foreground"
                                                        )}
                                                    >
                                                        {notif.title}
                                                    </p>
                                                    <span className="text-xs text-muted-foreground whitespace-nowrap">
                                                        {timeAgo(
                                                            notif.created_at
                                                        )}
                                                    </span>
                                                </div>
                                                {notif.message && (
                                                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                                                        {notif.message}
                                                    </p>
                                                )}
                                                <div className="flex gap-2 mt-1.5">
                                                    {notif.service_name && (
                                                        <Badge
                                                            variant="outline"
                                                            className="text-xs gap-1"
                                                        >
                                                            <Server className="h-3 w-3" />
                                                            {notif.service_name}
                                                        </Badge>
                                                    )}
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs"
                                                    >
                                                        {notif.type.replace(
                                                            /_/g,
                                                            " "
                                                        )}
                                                    </Badge>
                                                </div>
                                            </div>
                                            {!notif.is_read && (
                                                <div className="h-2 w-2 rounded-full bg-primary shrink-0 mt-2" />
                                            )}
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                )}
            </div>
        </>
    );
}
