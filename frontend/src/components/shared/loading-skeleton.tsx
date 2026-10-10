"use client";

/**
 * Squelettes de chargement avec reflet animé (classe .shimmer).
 */
import { cn } from "@/lib/utils";

export function Shimmer({ className }: { className?: string }) {
    return <div className={cn("shimmer rounded-xl", className)} />;
}

export function CardSkeleton({ className }: { className?: string }) {
    return (
        <div className={cn("glass rounded-2xl p-5", className)}>
            <div className="flex items-center justify-between">
                <div className="space-y-2.5">
                    <Shimmer className="h-3 w-20 rounded-md" />
                    <Shimmer className="h-8 w-24 rounded-lg" />
                    <Shimmer className="h-2.5 w-28 rounded-md" />
                </div>
                <Shimmer className="h-14 w-14 rounded-full" />
            </div>
        </div>
    );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
    return (
        <div className="space-y-2">
            {Array.from({ length: rows }).map((_, i) => (
                <Shimmer key={i} className="h-16 w-full" />
            ))}
        </div>
    );
}

export function PosterGridSkeleton({ count = 12, className }: { count?: number; className?: string }) {
    return (
        <div className={cn("grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-8", className)}>
            {Array.from({ length: count }).map((_, i) => (
                <div key={i} className="space-y-2">
                    <Shimmer className="aspect-[2/3] w-full rounded-2xl" />
                    <Shimmer className="h-3 w-3/4 rounded-md" />
                </div>
            ))}
        </div>
    );
}

export function PageSkeleton() {
    return (
        <div className="space-y-6">
            <Shimmer className="h-32 w-full rounded-3xl" />
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {Array.from({ length: 4 }).map((_, i) => (
                    <CardSkeleton key={i} />
                ))}
            </div>
            <div className="glass rounded-2xl p-5">
                <Shimmer className="mb-4 h-5 w-48 rounded-md" />
                <TableSkeleton />
            </div>
        </div>
    );
}
