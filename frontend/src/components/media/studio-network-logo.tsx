"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Film, Tv, Building2 } from "lucide-react";

export interface StudioNetworkLogoProps {
    name?: string | null;
    className?: string;
    variant?: "badge" | "hero" | "mini";
}

export function StudioNetworkLogo({ name, className, variant = "badge" }: StudioNetworkLogoProps) {
    if (!name) return null;

    const lower = String(name).toLowerCase().trim();

    // Brand Configurations
    let brandColorClass = "bg-card/70 text-foreground border-white/10";
    let brandName = typeof name === "string" ? name : String(name);
    let customSvg: React.ReactNode = null;

    if (lower.includes("netflix")) {
        brandName = "NETFLIX";
        brandColorClass = "bg-red-950/80 text-red-400 border-red-600/40 shadow-sm shadow-red-900/20 font-black tracking-widest";
        customSvg = (
            <span className="font-black text-red-500 text-xs mr-1 select-none">N</span>
        );
    } else if (lower.includes("hbo") || lower.includes("max")) {
        brandName = lower.includes("max") ? "MAX" : "HBO";
        brandColorClass = "bg-purple-950/80 text-purple-200 border-purple-500/40 font-bold tracking-wider";
    } else if (lower.includes("disney")) {
        brandName = "Disney+";
        brandColorClass = "bg-blue-950/80 text-sky-200 border-sky-400/40 font-bold italic";
    } else if (lower.includes("apple") || lower.includes("apple tv")) {
        brandName = "Apple TV+";
        brandColorClass = "bg-zinc-900/90 text-zinc-100 border-zinc-700/50 font-semibold";
    } else if (lower.includes("amazon") || lower.includes("prime")) {
        brandName = "Prime Video";
        brandColorClass = "bg-sky-950/80 text-sky-300 border-sky-500/40 font-bold";
    } else if (lower.includes("canal") || lower.includes("canal+")) {
        brandName = "CANAL+";
        brandColorClass = "bg-black text-white border-white/30 font-extrabold tracking-widest";
    } else if (lower.includes("hulu")) {
        brandName = "hulu";
        brandColorClass = "bg-emerald-950/80 text-emerald-400 border-emerald-500/40 font-bold lowercase";
    } else if (lower.includes("paramount")) {
        brandName = "Paramount+";
        brandColorClass = "bg-blue-900/70 text-blue-200 border-blue-400/40 font-bold";
    } else if (lower.includes("peacock")) {
        brandName = "Peacock";
        brandColorClass = "bg-gradient-to-r from-amber-950/60 via-emerald-950/60 to-purple-950/60 text-amber-200 border-amber-500/40 font-semibold";
    } else if (lower.includes("bbc")) {
        brandName = "BBC";
        brandColorClass = "bg-red-900/60 text-white border-red-500/40 font-bold tracking-widest";
    } else if (lower.includes("warner")) {
        brandName = "Warner Bros.";
        brandColorClass = "bg-blue-950/80 text-amber-300 border-amber-500/40 font-bold";
    } else if (lower.includes("marvel")) {
        brandName = "MARVEL STUDIOS";
        brandColorClass = "bg-red-700 text-white border-red-500 font-extrabold tracking-wider";
    } else if (lower.includes("pixar")) {
        brandName = "PIXAR";
        brandColorClass = "bg-sky-950/80 text-sky-100 border-sky-400/40 font-bold tracking-widest";
    } else if (lower.includes("20th century") || lower.includes("fox")) {
        brandName = "20th Century Studios";
        brandColorClass = "bg-amber-950/70 text-amber-200 border-amber-500/40 font-semibold";
    } else if (lower.includes("universal")) {
        brandName = "UNIVERSAL";
        brandColorClass = "bg-indigo-950/80 text-indigo-200 border-indigo-500/40 font-bold tracking-wider";
    } else if (lower.includes("sony") || lower.includes("columbia")) {
        brandName = "SONY PICTURES";
        brandColorClass = "bg-zinc-900 text-amber-300 border-amber-500/30 font-bold tracking-wider";
    } else if (lower.includes("a24")) {
        brandName = "A24";
        brandColorClass = "bg-zinc-950 text-zinc-100 border-zinc-700 font-black tracking-widest";
    }

    if (variant === "hero") {
        return (
            <Badge
                variant="outline"
                className={cn(
                    "px-3 py-1 text-xs border backdrop-blur-md transition-all hover:scale-105 flex items-center gap-1.5 shadow-md",
                    brandColorClass,
                    className
                )}
            >
                {customSvg || <Building2 className="h-3.5 w-3.5 opacity-80" />}
                <span>{brandName}</span>
            </Badge>
        );
    }

    return (
        <Badge
            variant="outline"
            className={cn(
                "text-[10px] px-2 py-0.5 border backdrop-blur-md flex items-center gap-1",
                brandColorClass,
                className
            )}
        >
            {customSvg}
            <span>{brandName}</span>
        </Badge>
    );
}
