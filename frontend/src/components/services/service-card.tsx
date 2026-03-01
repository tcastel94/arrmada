"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Film,
    Tv,
    Music,
    BookOpen,
    Search,
    Subtitles,
    PlayCircle,
    Download,
    MoreVertical,
    Trash2,
    Zap,
    Pencil,
} from "lucide-react";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { SERVICE_META, STATUS_COLORS } from "@/lib/constants";
import { ArrService } from "@/types/service";
import { motion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
    tv: Tv,
    film: Film,
    music: Music,
    "book-open": BookOpen,
    search: Search,
    subtitles: Subtitles,
    "play-circle": PlayCircle,
    download: Download,
};

interface ServiceCardProps {
    service: ArrService;
    onTest: (id: number) => void;
    onEdit: (service: ArrService) => void;
    onDelete: (id: number) => void;
    isTesting?: boolean;
}

export function ServiceCard({
    service,
    onTest,
    onEdit,
    onDelete,
    isTesting,
}: ServiceCardProps) {
    const meta = SERVICE_META[service.type] || {
        label: service.type,
        color: "#888",
        icon: "search",
    };
    const Icon = ICON_MAP[meta.icon] || Search;
    const statusColor = STATUS_COLORS[service.last_status] || STATUS_COLORS.unknown;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
        >
            <Card className="transition-all duration-200 hover:border-primary/20 hover:scale-[1.02]">
                <CardContent className="p-5">
                    <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                            <div
                                className="flex h-10 w-10 items-center justify-center rounded-lg"
                                style={{ backgroundColor: `${meta.color}20` }}
                            >
                                <Icon className="h-5 w-5" style={{ color: meta.color }} />
                            </div>
                            <div>
                                <h3 className="font-semibold">{service.name}</h3>
                                <p className="text-xs text-muted-foreground">{meta.label}</p>
                            </div>
                        </div>

                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8">
                                    <MoreVertical className="h-4 w-4" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={() => onTest(service.id)}>
                                    <Zap className="h-4 w-4 mr-2" />
                                    Tester la connexion
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => onEdit(service)}>
                                    <Pencil className="h-4 w-4 mr-2" />
                                    Modifier
                                </DropdownMenuItem>
                                <DropdownMenuItem
                                    onClick={() => onDelete(service.id)}
                                    className="text-destructive focus:text-destructive"
                                >
                                    <Trash2 className="h-4 w-4 mr-2" />
                                    Supprimer
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>
                    </div>

                    {/* URL & Status */}
                    <div className="mt-4 space-y-2">
                        <p className="text-xs text-muted-foreground truncate font-mono">
                            {service.url}
                        </p>

                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <span className={cn("h-2 w-2 rounded-full", statusColor)} />
                                <span className="text-sm capitalize">{service.last_status}</span>
                            </div>

                            {service.last_latency_ms !== null && (
                                <Badge variant="outline" className="text-xs">
                                    {service.last_latency_ms}ms
                                </Badge>
                            )}
                        </div>

                        {service.version && (
                            <p className="text-xs text-muted-foreground">
                                v{service.version}
                            </p>
                        )}
                    </div>

                    {/* Disabled badge */}
                    {!service.is_enabled && (
                        <Badge variant="secondary" className="mt-2">
                            Désactivé
                        </Badge>
                    )}
                </CardContent>
            </Card>
        </motion.div>
    );
}
