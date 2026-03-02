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
    Inbox,
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
    { icon: typeof Info; color: string; gradient: string; dot: string }
> = {
    info: {
        icon: Info,
        color: "text-blue-400",
        gradient: "from-blue-500/20 to-blue-500/5",
        dot: "bg-blue-400",
    },
    success: {
        icon: CheckCircle2,
        color: "text-emerald-400",
        gradient: "from-emerald-500/20 to-emerald-500/5",
        dot: "bg-emerald-400",
    },
    warning: {
        icon: AlertTriangle,
        color: "text-amber-400",
        gradient: "from-amber-500/20 to-amber-500/5",
        dot: "bg-amber-400",
    },
    error: {
        icon: AlertCircle,
        color: "text-red-400",
        gradient: "from-red-500/20 to-red-500/5",
        dot: "bg-red-400",
    },
};

function timeAgo(dateStr: string): string {
    const now = new Date();
    const date = new Date(dateStr);
    const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (seconds < 60) return "À l'instant";
    if (seconds < 3600) return `Il y a ${Math.floor(seconds / 60)}min`;
    if (seconds < 86400) return `Il y a ${Math.floor(seconds / 3600)}h`;
    if (seconds < 604800) return `Il y a ${Math.floor(seconds / 86400)}j`;
    return date.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};
const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" } },
};

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
            <motion.div
                className="p-4 md:p-6 max-w-3xl mx-auto space-y-5"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero Header */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-rose-600/20 via-pink-600/10 to-transparent ring-1 ring-white/5 p-6">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                                <div className="relative">
                                    <div className="rounded-xl bg-rose-500/20 p-3">
                                        <Bell className="h-6 w-6 text-rose-400" />
                                    </div>
                                    {unreadCount > 0 && (
                                        <span className="absolute -top-1 -right-1 h-5 w-5 rounded-full bg-rose-500 text-white text-[10px] font-bold flex items-center justify-center ring-2 ring-background">
                                            {unreadCount > 9 ? "9+" : unreadCount}
                                        </span>
                                    )}
                                </div>
                                <div>
                                    <h2 className="text-2xl font-bold tracking-tight">
                                        Notifications
                                    </h2>
                                    <p className="text-sm text-muted-foreground mt-0.5">
                                        {unreadCount > 0
                                            ? `${unreadCount} non lue${unreadCount > 1 ? "s" : ""}`
                                            : "Tout est lu ✨"}
                                    </p>
                                </div>
                            </div>
                            {unreadCount > 0 && (
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => markAllRead.mutate()}
                                    className="gap-1.5 border-white/10 hover:bg-white/5"
                                >
                                    <CheckCheck className="h-3.5 w-3.5" />
                                    Tout marquer lu
                                </Button>
                            )}
                        </div>
                        <div className="absolute -top-16 -right-16 w-48 h-48 rounded-full bg-rose-500/10 blur-3xl" />
                    </div>
                </motion.div>

                {/* Notifications List */}
                {notifications.length === 0 ? (
                    <motion.div variants={fadeUp}>
                        <div className="rounded-xl ring-1 ring-white/5 bg-card/30 p-12">
                            <EmptyState
                                icon={Inbox}
                                title="Aucune notification"
                                description="Les alertes de services, syncs TRaSH et autres événements apparaîtront ici"
                            />
                        </div>
                    </motion.div>
                ) : (
                    <motion.div className="space-y-2" variants={container}>
                        {notifications.map((notif) => {
                            const config =
                                SEVERITY_CONFIG[notif.severity] ??
                                SEVERITY_CONFIG.info;
                            const Icon = config.icon;

                            return (
                                <motion.div key={notif.id} variants={fadeUp}>
                                    <Card
                                        className={cn(
                                            "border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm cursor-pointer overflow-hidden",
                                            "hover:ring-white/10 transition-all duration-200",
                                            !notif.is_read && "ring-primary/30"
                                        )}
                                        onClick={() => {
                                            if (!notif.is_read)
                                                markRead.mutate(notif.id);
                                        }}
                                    >
                                        <CardContent className="flex items-start gap-3 p-4">
                                            {/* Icon */}
                                            <div
                                                className={cn(
                                                    "rounded-lg p-2 shrink-0 bg-gradient-to-br",
                                                    config.gradient
                                                )}
                                            >
                                                <Icon
                                                    className={cn(
                                                        "h-4 w-4",
                                                        config.color
                                                    )}
                                                />
                                            </div>

                                            {/* Content */}
                                            <div className="flex-1 min-w-0">
                                                <div className="flex items-center justify-between gap-2">
                                                    <p
                                                        className={cn(
                                                            "text-sm truncate",
                                                            !notif.is_read
                                                                ? "font-semibold"
                                                                : "font-medium text-muted-foreground"
                                                        )}
                                                    >
                                                        {notif.title}
                                                    </p>
                                                    <span className="text-[10px] text-muted-foreground/60 whitespace-nowrap tabular-nums">
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
                                                <div className="flex gap-1.5 mt-2">
                                                    {notif.service_name && (
                                                        <Badge
                                                            variant="outline"
                                                            className="text-[10px] gap-1 h-4 px-1.5 border-white/10"
                                                        >
                                                            <Server className="h-2.5 w-2.5" />
                                                            {notif.service_name}
                                                        </Badge>
                                                    )}
                                                    <Badge
                                                        variant="outline"
                                                        className="text-[10px] h-4 px-1.5 border-white/10"
                                                    >
                                                        {notif.type.replace(
                                                            /_/g,
                                                            " "
                                                        )}
                                                    </Badge>
                                                </div>
                                            </div>

                                            {/* Unread dot */}
                                            {!notif.is_read && (
                                                <div className="relative shrink-0 mt-1.5">
                                                    <div
                                                        className={cn(
                                                            "h-2 w-2 rounded-full",
                                                            config.dot
                                                        )}
                                                    />
                                                    <div
                                                        className={cn(
                                                            "absolute inset-0 rounded-full animate-ping opacity-40",
                                                            config.dot
                                                        )}
                                                    />
                                                </div>
                                            )}
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </motion.div>
                )}
            </motion.div>
        </>
    );
}
