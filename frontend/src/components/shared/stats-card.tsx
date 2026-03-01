"use client";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { LucideIcon } from "lucide-react";
import { motion } from "framer-motion";

interface StatsCardProps {
    title: string;
    value: string | number;
    icon: LucideIcon;
    trend?: {
        value: number;
        label: string;
    };
    className?: string;
}

export function StatsCard({
    title,
    value,
    icon: Icon,
    trend,
    className,
}: StatsCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
        >
            <Card
                className={cn(
                    "transition-all duration-200 hover:scale-[1.02] hover:border-primary/20",
                    className
                )}
            >
                <CardContent className="p-6">
                    <div className="flex items-center justify-between">
                        <div className="space-y-1">
                            <p className="text-sm font-medium text-muted-foreground">
                                {title}
                            </p>
                            <p className="text-2xl font-bold tracking-tight">{value}</p>
                            {trend && (
                                <p
                                    className={cn(
                                        "text-xs",
                                        trend.value >= 0 ? "text-green-500" : "text-red-500"
                                    )}
                                >
                                    {trend.value >= 0 ? "+" : ""}
                                    {trend.value} {trend.label}
                                </p>
                            )}
                        </div>
                        <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-primary/10">
                            <Icon className="h-6 w-6 text-primary" />
                        </div>
                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
}
