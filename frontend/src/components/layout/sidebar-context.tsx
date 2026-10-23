"use client";

/**
 * État partagé de la sidebar (repliée / dépliée), mémorisé dans le
 * navigateur. Avant, replier la sidebar laissait un grand vide à gauche
 * car le contenu principal gardait sa marge fixe de 260 px.
 */
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

const STORAGE_KEY = "arrmada.sidebar.collapsed";

interface SidebarCtx {
    collapsed: boolean;
    toggle: () => void;
}

const Ctx = createContext<SidebarCtx>({ collapsed: false, toggle: () => {} });

export function SidebarProvider({ children }: { children: ReactNode }) {
    const [collapsed, setCollapsed] = useState(false);

    useEffect(() => {
        try {
            setCollapsed(localStorage.getItem(STORAGE_KEY) === "1");
        } catch {
            /* stockage indisponible (navigation privée) : on garde la valeur par défaut */
        }
    }, []);

    const toggle = useCallback(() => {
        setCollapsed((c) => {
            try {
                localStorage.setItem(STORAGE_KEY, c ? "0" : "1");
            } catch {
                /* ignore */
            }
            return !c;
        });
    }, []);

    return <Ctx.Provider value={{ collapsed, toggle }}>{children}</Ctx.Provider>;
}

export const useSidebar = () => useContext(Ctx);

export const SIDEBAR_WIDTH = 240;
export const SIDEBAR_COLLAPSED_WIDTH = 64;
