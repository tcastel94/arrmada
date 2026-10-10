"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Sparkles, Disc, Radio, Tv, Volume2 } from "lucide-react";

export interface MediaTechSpecs {
    resolution?: string | number | null;
    quality?: string | null;
    video_codec?: string | null;
    video_dynamic_range?: string | null;
    audio_codec?: string | null;
    audio_channels?: number | null;
    edition?: string | null;
    release_group?: string | null;
}

export interface MediaTechBadgesProps {
    specs?: MediaTechSpecs | null;
    className?: string;
    variant?: "hero" | "card" | "mini" | "inline";
    showLabels?: boolean;
}

// ── SVG Icon Components for Audio & Video Standards ────────────────────────

export function Icon4K({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg viewBox="0 0 48 24" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
            <rect width="48" height="24" rx="4" fill="currentColor" fillOpacity="0.1" />
            <path d="M7 17V7H10V12.2L13.8 7H17.2L12.5 12.8L17.5 17H14L10 13.3V17H7Z" fill="currentColor" />
            <path d="M26 13.5V7H29V17H26.3L21.8 10.2V17H19V7H21.8L26 13.5Z" fill="currentColor" stroke="currentColor" strokeWidth="0.5" />
            <path d="M37 7H41.5C43.5 7 45 8.2 45 10C45 11.2 44.2 12.1 43.1 12.6L46 17H42.5L39.9 13H39.5V17H37V7ZM39.5 11H41.2C42 11 42.6 10.6 42.6 10C42.6 9.4 42 9 41.2 9H39.5V11Z" fill="currentColor" />
        </svg>
    );
}

export function IconDolby({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg viewBox="0 0 32 20" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
            <rect width="32" height="20" rx="3" fill="currentColor" fillOpacity="0.15" />
            <path d="M5 4H10C12.8 4 14.5 5.8 14.5 10C14.5 14.2 12.8 16 10 16H5V4ZM9.2 13.2C10.7 13.2 11.8 12.1 11.8 10C11.8 7.9 10.7 6.8 9.2 6.8H7.7V13.2H9.2Z" fill="currentColor" />
            <path d="M27 4H22C19.2 4 17.5 5.8 17.5 10C17.5 14.2 19.2 16 22 16H27V4ZM22.8 13.2C21.3 13.2 20.2 12.1 20.2 10C20.2 7.9 21.3 6.8 22.8 6.8H24.3V13.2H22.8Z" fill="currentColor" />
        </svg>
    );
}

export function IconDTS({ className = "h-4 w-4" }: { className?: string }) {
    return (
        <svg viewBox="0 0 44 18" fill="none" className={className} xmlns="http://www.w3.org/2000/svg">
            <path d="M2 3H8.5C12.5 3 15 5.5 15 9C15 12.5 12.5 15 8.5 15H2V3ZM6.5 12.2H8.3C10.5 12.2 11.8 11 11.8 9C11.8 7 10.5 5.8 8.3 5.8H6.5V12.2Z" fill="currentColor" />
            <path d="M19.5 5.8H16V3H26V5.8H22.5V15H19.5V5.8Z" fill="currentColor" />
            <path d="M27.5 12.5C28.2 14 29.8 15 32 15C34.2 15 35.8 13.8 35.8 12.2C35.8 10.2 33.5 9.8 31.5 9.3C29 8.7 27.8 8 27.8 6.2C27.8 4.6 29.5 3.5 31.8 3.5C34 3.5 35.5 4.5 36.2 6L33.8 7.2C33.3 6.2 32.5 5.8 31.5 5.8C30.6 5.8 29.8 6.3 29.8 7.1C29.8 8 31.5 8.3 33.8 8.9C36.2 9.5 37.8 10.5 37.8 12.3C37.8 14.5 35.5 15.8 32.2 15.8C29.5 15.8 27.5 14.4 26.5 12.2L27.5 12.5Z" fill="currentColor" />
        </svg>
    );
}

// Defensive helper parsing logic
export function parseTechSpecs(specs?: MediaTechSpecs | null) {
    if (!specs) {
        return {
            resLabel: null,
            resBadgeClass: "",
            is4K: false,
            hdrLabel: null,
            hdrBadgeClass: "",
            audioLabel: null,
            audioBadgeClass: "",
            isAtmos: false,
            isDTS: false,
            channelLabel: null,
            sourceLabel: null,
            sourceBadgeClass: "",
            codecLabel: null,
        };
    }

    const rawQuality = String(specs.quality ?? "").toLowerCase();
    const rawRes = (String(specs.resolution ?? "") + " " + rawQuality).toLowerCase();
    const rawVCodec = String(specs.video_codec ?? "").toLowerCase();
    const rawHDR = String(specs.video_dynamic_range ?? specs.video_codec ?? "").toLowerCase();
    const rawACodec = String(specs.audio_codec ?? "").toLowerCase();
    const channels = specs.audio_channels;

    // 1. Resolution
    let resLabel: string | null = null;
    let resBadgeClass = "";
    let is4K = false;

    if (rawRes.includes("2160") || rawRes.includes("4k") || rawRes.includes("uhd")) {
        resLabel = "4K UHD";
        resBadgeClass = "bg-gradient-to-r from-amber-500/20 via-yellow-500/20 to-amber-600/30 text-amber-300 border-amber-500/40 shadow-sm shadow-amber-500/10 font-bold";
        is4K = true;
    } else if (rawRes.includes("1080")) {
        resLabel = "1080p FHD";
        resBadgeClass = "bg-sky-500/15 text-sky-300 border-sky-500/30 font-medium";
    } else if (rawRes.includes("720")) {
        resLabel = "720p HD";
        resBadgeClass = "bg-teal-500/15 text-teal-300 border-teal-500/30 font-medium";
    } else if (rawRes.includes("480") || rawRes.includes("576") || rawRes.includes("sd")) {
        resLabel = "SD";
        resBadgeClass = "bg-slate-500/15 text-slate-300 border-slate-500/30";
    }

    // 2. Dynamic Range / HDR
    let hdrLabel: string | null = null;
    let hdrBadgeClass = "";

    if (rawHDR.includes("dv") || rawHDR.includes("dolby vision") || rawHDR.includes("dovi")) {
        hdrLabel = "Dolby Vision";
        hdrBadgeClass = "bg-gradient-to-r from-purple-900/60 to-indigo-900/60 text-purple-200 border-purple-400/40 font-semibold shadow-purple-500/10";
    } else if (rawHDR.includes("hdr10+") || rawHDR.includes("hdr10plus")) {
        hdrLabel = "HDR10+";
        hdrBadgeClass = "bg-amber-500/20 text-amber-300 border-amber-400/40 font-semibold";
    } else if (rawHDR.includes("hdr10") || rawHDR.includes("hdr")) {
        hdrLabel = "HDR10";
        hdrBadgeClass = "bg-amber-500/15 text-amber-400 border-amber-500/30 font-semibold";
    }

    // 3. Audio Codec & Technology
    let audioLabel: string | null = null;
    let audioBadgeClass = "";
    let isAtmos = false;
    let isDTS = false;

    if (rawACodec.includes("atmos")) {
        audioLabel = "Dolby Atmos";
        audioBadgeClass = "bg-gradient-to-r from-cyan-950/70 via-blue-900/60 to-indigo-950/70 text-cyan-200 border-cyan-400/40 font-semibold shadow-cyan-500/10";
        isAtmos = true;
    } else if (rawACodec.includes("dts-x") || rawACodec.includes("dtsx")) {
        audioLabel = "DTS:X";
        audioBadgeClass = "bg-gradient-to-r from-red-950/70 via-orange-950/60 to-red-900/70 text-orange-300 border-orange-500/40 font-semibold";
        isDTS = true;
    } else if (rawACodec.includes("dts-hd") || rawACodec.includes("dtshd") || rawACodec.includes("ma")) {
        audioLabel = "DTS-HD MA";
        audioBadgeClass = "bg-orange-950/50 text-orange-300 border-orange-500/30 font-medium";
        isDTS = true;
    } else if (rawACodec.includes("dts")) {
        audioLabel = "DTS";
        audioBadgeClass = "bg-orange-950/40 text-orange-400 border-orange-500/30";
        isDTS = true;
    } else if (rawACodec.includes("truehd")) {
        audioLabel = "Dolby TrueHD";
        audioBadgeClass = "bg-blue-950/50 text-blue-300 border-blue-400/30 font-medium";
    } else if (rawACodec.includes("eac3") || rawACodec.includes("dd+") || rawACodec.includes("digital+")) {
        audioLabel = "Dolby Digital+";
        audioBadgeClass = "bg-blue-950/40 text-blue-300 border-blue-400/30";
    } else if (rawACodec.includes("ac3") || rawACodec.includes("dd") || rawACodec.includes("digital")) {
        audioLabel = "Dolby Digital";
        audioBadgeClass = "bg-slate-900/60 text-slate-200 border-slate-700/50";
    } else if (rawACodec.includes("flac")) {
        audioLabel = "FLAC Lossless";
        audioBadgeClass = "bg-emerald-950/40 text-emerald-300 border-emerald-500/30";
    } else if (rawACodec.includes("aac")) {
        audioLabel = "AAC";
        audioBadgeClass = "bg-slate-900/40 text-slate-300 border-slate-700/40";
    }

    // 4. Audio Channels
    let channelLabel: string | null = null;
    if (channels === 8 || channels === 7.1) {
        channelLabel = "7.1";
    } else if (channels === 6 || channels === 5.1) {
        channelLabel = "5.1";
    } else if (channels === 2 || channels === 2.0) {
        channelLabel = "2.0";
    }

    // 5. Source / Quality Type
    let sourceLabel: string | null = null;
    let sourceBadgeClass = "bg-slate-800/40 text-slate-300 border-slate-700/40";

    if (rawQuality.includes("remux")) {
        sourceLabel = "BD-Remux";
        sourceBadgeClass = "bg-indigo-500/20 text-indigo-300 border-indigo-500/40 font-medium";
    } else if (rawQuality.includes("bluray") || rawQuality.includes("bdrip")) {
        sourceLabel = "BluRay";
        sourceBadgeClass = "bg-blue-500/15 text-blue-300 border-blue-500/30";
    } else if (rawQuality.includes("web-dl") || rawQuality.includes("webdl")) {
        sourceLabel = "WEB-DL";
        sourceBadgeClass = "bg-sky-500/15 text-sky-300 border-sky-500/30";
    } else if (rawQuality.includes("webrip")) {
        sourceLabel = "WEBRip";
        sourceBadgeClass = "bg-teal-500/15 text-teal-300 border-teal-500/30";
    } else if (rawQuality.includes("hdtv")) {
        sourceLabel = "HDTV";
        sourceBadgeClass = "bg-slate-500/15 text-slate-300 border-slate-500/30";
    }

    // 6. Video Codec
    let codecLabel: string | null = null;
    if (rawVCodec.includes("hevc") || rawVCodec.includes("h265") || rawVCodec.includes("x265")) {
        codecLabel = "HEVC / x265";
    } else if (rawVCodec.includes("avc") || rawVCodec.includes("h264") || rawVCodec.includes("x264")) {
        codecLabel = "AVC / x264";
    } else if (rawVCodec.includes("av1")) {
        codecLabel = "AV1";
    }

    return {
        resLabel,
        resBadgeClass,
        is4K,
        hdrLabel,
        hdrBadgeClass,
        audioLabel,
        audioBadgeClass,
        isAtmos,
        isDTS,
        channelLabel,
        sourceLabel,
        sourceBadgeClass,
        codecLabel,
    };
}

export function MediaTechBadges({ specs, className, variant = "hero" }: MediaTechBadgesProps) {
    if (!specs) return null;
    const parsed = parseTechSpecs(specs);

    if (!parsed || (!parsed.resLabel && !parsed.hdrLabel && !parsed.audioLabel && !parsed.sourceLabel && !specs.quality)) {
        return null;
    }

    // Compact Card View (Used inside Media Library Grid cards)
    if (variant === "card") {
        return (
            <div className={cn("flex flex-wrap gap-1 items-center", className)}>
                {parsed.resLabel && (
                    <Badge className={cn("text-[10px] px-1.5 py-0.5 border backdrop-blur-md", parsed.resBadgeClass)}>
                        {parsed.is4K && <Sparkles className="h-2.5 w-2.5 mr-1 text-amber-300 animate-pulse" />}
                        {parsed.resLabel}
                    </Badge>
                )}
                {parsed.hdrLabel && (
                    <Badge className={cn("text-[10px] px-1.5 py-0.5 border backdrop-blur-md", parsed.hdrBadgeClass)}>
                        {parsed.hdrLabel}
                    </Badge>
                )}
                {parsed.audioLabel && (
                    <Badge className={cn("text-[10px] px-1.5 py-0.5 border backdrop-blur-md", parsed.audioBadgeClass)}>
                        {parsed.isDTS ? <IconDTS className="h-2.5 w-5 mr-1" /> : parsed.audioLabel.includes("Dolby") ? <IconDolby className="h-2.5 w-4 mr-1" /> : null}
                        {parsed.audioLabel}
                        {parsed.channelLabel ? ` ${parsed.channelLabel}` : ""}
                    </Badge>
                )}
            </div>
        );
    }

    // Mini Inline View
    if (variant === "mini" || variant === "inline") {
        return (
            <div className={cn("inline-flex flex-wrap items-center gap-1.5 text-xs", className)}>
                {parsed.resLabel && (
                    <Badge variant="outline" className={cn("text-[11px] py-0.5", parsed.resBadgeClass)}>
                        {parsed.resLabel}
                    </Badge>
                )}
                {parsed.hdrLabel && (
                    <Badge variant="outline" className={cn("text-[11px] py-0.5", parsed.hdrBadgeClass)}>
                        {parsed.hdrLabel}
                    </Badge>
                )}
                {parsed.audioLabel && (
                    <Badge variant="outline" className={cn("text-[11px] py-0.5", parsed.audioBadgeClass)}>
                        {parsed.audioLabel}
                    </Badge>
                )}
            </div>
        );
    }

    // Full Rich Hero View (Used in Media Detail Page header)
    return (
        <div className={cn("flex flex-wrap items-center gap-2 py-1", className)}>
            {/* Resolution */}
            {parsed.resLabel ? (
                <Badge
                    variant="outline"
                    className={cn(
                        "px-2.5 py-1 text-xs border backdrop-blur-md transition-all hover:scale-105 flex items-center gap-1.5",
                        parsed.resBadgeClass
                    )}
                >
                    {parsed.is4K ? <Icon4K className="h-4 w-7 text-amber-300" /> : <Tv className="h-3.5 w-3.5" />}
                    <span>{parsed.resLabel}</span>
                </Badge>
            ) : specs.quality ? (
                <Badge variant="outline" className="px-2.5 py-1 text-xs bg-card/60 backdrop-blur-md border-white/10">
                    {specs.quality}
                </Badge>
            ) : null}

            {/* Dynamic Range / HDR */}
            {parsed.hdrLabel && (
                <Badge
                    variant="outline"
                    className={cn(
                        "px-2.5 py-1 text-xs border backdrop-blur-md transition-all hover:scale-105 flex items-center gap-1.5",
                        parsed.hdrBadgeClass
                    )}
                >
                    {parsed.hdrLabel.includes("Dolby") ? <IconDolby className="h-3.5 w-5 text-purple-300" /> : <Sparkles className="h-3.5 w-3.5 text-amber-400" />}
                    <span>{parsed.hdrLabel}</span>
                </Badge>
            )}

            {/* Audio Codec & Surround */}
            {parsed.audioLabel && (
                <Badge
                    variant="outline"
                    className={cn(
                        "px-2.5 py-1 text-xs border backdrop-blur-md transition-all hover:scale-105 flex items-center gap-1.5",
                        parsed.audioBadgeClass
                    )}
                >
                    {parsed.isDTS ? (
                        <IconDTS className="h-3.5 w-8 text-orange-400" />
                    ) : parsed.audioLabel.includes("Dolby") ? (
                        <IconDolby className="h-3.5 w-5 text-cyan-300" />
                    ) : (
                        <Volume2 className="h-3.5 w-3.5" />
                    )}
                    <span>
                        {parsed.audioLabel}
                        {parsed.channelLabel ? ` ${parsed.channelLabel}` : ""}
                    </span>
                </Badge>
            )}

            {/* Source / Remux */}
            {parsed.sourceLabel && (
                <Badge
                    variant="outline"
                    className={cn(
                        "px-2.5 py-1 text-xs border backdrop-blur-md transition-all hover:scale-105 flex items-center gap-1.5",
                        parsed.sourceBadgeClass
                    )}
                >
                    <Disc className="h-3.5 w-3.5" />
                    <span>{parsed.sourceLabel}</span>
                </Badge>
            )}

            {/* Video Codec */}
            {parsed.codecLabel && (
                <Badge
                    variant="outline"
                    className="px-2.5 py-1 text-xs bg-slate-900/50 text-slate-300 border-slate-700/50 backdrop-blur-md flex items-center gap-1.5"
                >
                    <Radio className="h-3.5 w-3.5 text-slate-400" />
                    <span>{parsed.codecLabel}</span>
                </Badge>
            )}

            {/* Edition */}
            {specs.edition && (
                <Badge variant="secondary" className="px-2.5 py-1 text-xs bg-violet-500/20 text-violet-300 border-violet-500/30">
                    {specs.edition}
                </Badge>
            )}
        </div>
    );
}
