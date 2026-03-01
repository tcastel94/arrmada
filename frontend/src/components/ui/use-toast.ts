"use client";

import { useState, useCallback } from "react";

interface Toast {
    id: string;
    title: string;
    description?: string;
    variant?: "default" | "destructive";
}

let toastCounter = 0;
let globalAddToast: ((toast: Omit<Toast, "id">) => void) | null = null;

export function useToast() {
    const [toasts, setToasts] = useState<Toast[]>([]);

    const addToast = useCallback(
        (toast: Omit<Toast, "id">) => {
            const id = `toast-${++toastCounter}`;
            setToasts((prev) => [...prev, { ...toast, id }]);
            // Auto-dismiss after 4 seconds
            setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== id));
            }, 4000);
        },
        []
    );

    globalAddToast = addToast;

    return {
        toasts,
        toast: addToast,
        dismiss: (id: string) =>
            setToasts((prev) => prev.filter((t) => t.id !== id)),
    };
}

export { type Toast };
