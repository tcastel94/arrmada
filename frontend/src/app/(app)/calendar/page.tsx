"use client";

import { Header } from "@/components/layout/header";
import { PageSkeleton } from "@/components/shared/loading-skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    CalendarDays,
    Film,
    Tv,
    ChevronLeft,
    ChevronRight,
    Check,
    Clock,
    Eye,
} from "lucide-react";
import { useCalendar, CalendarEntry } from "@/hooks/use-new-features";
import { cn } from "@/lib/utils";
import { motion } from "framer-motion";
import { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";

const container = {
    hidden: { opacity: 0 },
    show: { opacity: 1, transition: { staggerChildren: 0.04 } },
};

const fadeUp = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};

function getDaysInMonth(year: number, month: number): Date[] {
    const days: Date[] = [];
    const date = new Date(year, month, 1);
    while (date.getMonth() === month) {
        days.push(new Date(date));
        date.setDate(date.getDate() + 1);
    }
    return days;
}

function formatDateKey(d: Date): string {
    return d.toISOString().slice(0, 10);
}

const MONTH_NAMES = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
];

const DAY_NAMES = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

export default function CalendarPage() {
    const [currentDate, setCurrentDate] = useState(new Date());
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const { data, isLoading } = useCalendar(90);

    const days = useMemo(() => getDaysInMonth(year, month), [year, month]);
    const firstDayOffset = (days[0].getDay() + 6) % 7; // Monday = 0

    const eventsByDate = useMemo(() => {
        return data?.by_date ?? {};
    }, [data]);

    const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
    const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1));
    const today = formatDateKey(new Date());

    if (isLoading) {
        return (
            <>
                <Header title="Calendrier" />
                <div className="p-6"><PageSkeleton /></div>
            </>
        );
    }

    return (
        <>
            <Header title="Calendrier" />
            <motion.div
                className="p-4 md:p-6 space-y-5 max-w-[1400px] mx-auto"
                variants={container}
                initial="hidden"
                animate="show"
            >
                {/* Hero */}
                <motion.div variants={fadeUp}>
                    <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-indigo-600/20 via-purple-600/10 to-transparent p-6 ring-1 ring-indigo-500/20">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-2xl font-bold flex items-center gap-2">
                                    <CalendarDays className="h-6 w-6 text-indigo-400" />
                                    {MONTH_NAMES[month]} {year}
                                </h2>
                                <p className="text-sm text-muted-foreground mt-1">
                                    {data?.total ?? 0} sorties à venir
                                </p>
                            </div>
                            <div className="flex gap-2">
                                <Button variant="outline" size="icon" onClick={prevMonth} className="h-8 w-8">
                                    <ChevronLeft className="h-4 w-4" />
                                </Button>
                                <Button variant="outline" size="sm" onClick={() => setCurrentDate(new Date())} className="h-8 text-xs">
                                    Aujourd&apos;hui
                                </Button>
                                <Button variant="outline" size="icon" onClick={nextMonth} className="h-8 w-8">
                                    <ChevronRight className="h-4 w-4" />
                                </Button>
                            </div>
                        </div>
                        <div className="absolute -top-16 -right-16 w-40 h-40 rounded-full blur-3xl opacity-20 bg-indigo-500/30" />
                    </div>
                </motion.div>

                {/* Calendar Grid */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm overflow-hidden">
                        <CardContent className="p-0">
                            {/* Day Headers */}
                            <div className="grid grid-cols-7 border-b border-white/5">
                                {DAY_NAMES.map((day) => (
                                    <div key={day} className="px-2 py-2 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                                        {day}
                                    </div>
                                ))}
                            </div>

                            {/* Calendar Days */}
                            <div className="grid grid-cols-7">
                                {/* Empty cells for offset */}
                                {Array.from({ length: firstDayOffset }).map((_, i) => (
                                    <div key={`empty-${i}`} className="min-h-[100px] border-b border-r border-white/5 bg-card/20" />
                                ))}

                                {days.map((day) => {
                                    const key = formatDateKey(day);
                                    const events: CalendarEntry[] = eventsByDate[key] || [];
                                    const isToday = key === today;
                                    const isPast = key < today;

                                    return (
                                        <div
                                            key={key}
                                            className={cn(
                                                "min-h-[100px] border-b border-r border-white/5 p-1.5 transition-colors",
                                                isToday && "bg-indigo-500/5 ring-1 ring-inset ring-indigo-500/20",
                                                isPast && "opacity-60",
                                                events.length > 0 && "hover:bg-white/[0.02]",
                                            )}
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <span className={cn(
                                                    "text-xs font-medium tabular-nums",
                                                    isToday && "text-indigo-400 font-bold",
                                                )}>
                                                    {day.getDate()}
                                                </span>
                                                {events.length > 0 && (
                                                    <Badge variant="outline" className="text-[9px] px-1 h-4 border-indigo-500/30 text-indigo-400">
                                                        {events.length}
                                                    </Badge>
                                                )}
                                            </div>

                                            {/* Event items */}
                                            <div className="space-y-0.5">
                                                {events.slice(0, 3).map((event) => (
                                                    <div
                                                        key={event.id}
                                                        className={cn(
                                                            "text-[10px] px-1 py-0.5 rounded truncate",
                                                            event.type === "episode"
                                                                ? "bg-blue-500/10 text-blue-400"
                                                                : "bg-violet-500/10 text-violet-400",
                                                            event.has_file && "bg-emerald-500/10 text-emerald-400",
                                                        )}
                                                        title={`${event.title} ${event.label}`}
                                                    >
                                                        {event.type === "episode" ? (
                                                            <span className="flex items-center gap-0.5">
                                                                <Tv className="h-2.5 w-2.5 shrink-0" />
                                                                {event.label}
                                                            </span>
                                                        ) : (
                                                            <span className="flex items-center gap-0.5">
                                                                <Film className="h-2.5 w-2.5 shrink-0" />
                                                                {event.title.slice(0, 12)}
                                                            </span>
                                                        )}
                                                    </div>
                                                ))}
                                                {events.length > 3 && (
                                                    <span className="text-[9px] text-muted-foreground px-1">
                                                        +{events.length - 3} de plus
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>

                {/* Upcoming List */}
                <motion.div variants={fadeUp}>
                    <Card className="border-0 ring-1 ring-white/5 bg-card/40 backdrop-blur-sm">
                        <CardContent className="p-0">
                            <div className="flex items-center gap-2 px-5 py-3 border-b border-white/5">
                                <Clock className="h-4 w-4 text-indigo-400" />
                                <span className="text-sm font-semibold">Prochaines sorties</span>
                            </div>
                            <div className="divide-y divide-white/5">
                                {(data?.items ?? [])
                                    .filter((e) => (e.air_date ?? "") >= today)
                                    .slice(0, 15)
                                    .map((entry) => (
                                        <div key={entry.id} className="flex items-center gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors">
                                            {entry.poster_url ? (
                                                <img
                                                    src={entry.poster_url}
                                                    alt={entry.title}
                                                    className="h-12 w-8 rounded object-cover ring-1 ring-white/10"
                                                />
                                            ) : (
                                                <div className="h-12 w-8 rounded bg-muted/20 flex items-center justify-center">
                                                    {entry.type === "episode" ? (
                                                        <Tv className="h-4 w-4 text-muted-foreground" />
                                                    ) : (
                                                        <Film className="h-4 w-4 text-muted-foreground" />
                                                    )}
                                                </div>
                                            )}
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium truncate">{entry.title}</p>
                                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                                    {entry.label && <span>{entry.label}</span>}
                                                    {entry.subtitle && <span>— {entry.subtitle}</span>}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {entry.has_file ? (
                                                    <Badge className="bg-emerald-500/20 text-emerald-400 border-0 text-[10px]">
                                                        <Check className="h-3 w-3 mr-0.5" /> Téléchargé
                                                    </Badge>
                                                ) : entry.monitored ? (
                                                    <Badge className="bg-blue-500/20 text-blue-400 border-0 text-[10px]">
                                                        <Eye className="h-3 w-3 mr-0.5" /> Surveillé
                                                    </Badge>
                                                ) : null}
                                                <span className="text-xs text-muted-foreground tabular-nums whitespace-nowrap">
                                                    {(entry.air_date ?? "").slice(0, 10)}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                            </div>
                        </CardContent>
                    </Card>
                </motion.div>
            </motion.div>
        </>
    );
}
