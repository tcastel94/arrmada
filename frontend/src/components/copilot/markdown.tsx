"use client";

/**
 * Rendu Markdown des réponses du copilote (titres, listes, tableaux, code).
 * react-markdown construit des éléments React : aucun HTML brut du modèle
 * n'est injecté dans la page.
 */
import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
    p: ({ children }) => <p className="leading-relaxed [&:not(:first-child)]:mt-3">{children}</p>,
    h1: ({ children }) => <h3 className="mt-5 text-[17px] font-semibold tracking-tight first:mt-0">{children}</h3>,
    h2: ({ children }) => <h3 className="mt-5 text-[17px] font-semibold tracking-tight first:mt-0">{children}</h3>,
    h3: ({ children }) => <h4 className="mt-4 text-[15px] font-semibold first:mt-0">{children}</h4>,
    h4: ({ children }) => <h5 className="mt-4 text-[15px] font-semibold text-muted-foreground first:mt-0">{children}</h5>,
    ul: ({ children }) => <ul className="mt-2 list-disc space-y-1 pl-5 marker:text-muted-foreground">{children}</ul>,
    ol: ({ children }) => <ol className="mt-2 list-decimal space-y-1 pl-5 marker:text-muted-foreground">{children}</ol>,
    li: ({ children }) => <li className="leading-relaxed [&>p]:mt-0">{children}</li>,
    strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
    a: ({ href, children }) => (
        <a href={href} target="_blank" rel="noreferrer noopener" className="text-primary underline-offset-2 hover:underline [overflow-wrap:anywhere]">
            {children}
        </a>
    ),
    blockquote: ({ children }) => <blockquote className="mt-3 border-l-2 border-white/15 pl-3 text-muted-foreground">{children}</blockquote>,
    hr: () => <hr className="my-4 border-white/[0.08]" />,
    code: ({ children }) => <code className="rounded bg-white/[0.08] px-1 py-px font-mono text-[13px] [overflow-wrap:anywhere]">{children}</code>,
    // Bloc de code : le <code> intérieur perd son fond de « code en ligne »
    pre: ({ children }) => (
        <pre className="mt-3 overflow-x-auto rounded-xl bg-black/40 p-3 text-[13px] leading-relaxed ring-1 ring-white/[0.06] [&_code]:bg-transparent [&_code]:p-0 [&_code]:[overflow-wrap:normal]">
            {children}
        </pre>
    ),
    // Tableau : défile horizontalement sur mobile plutôt que d'écraser la page
    table: ({ children }) => (
        <div className="mt-3 overflow-x-auto rounded-xl ring-1 ring-white/[0.08]">
            <table className="w-full border-collapse text-left text-[13px]">{children}</table>
        </div>
    ),
    thead: ({ children }) => <thead className="bg-white/[0.05] text-muted-foreground">{children}</thead>,
    // scope="col" : annoncé comme en-tête de colonne par les lecteurs d'écran
    th: ({ children }) => (
        <th scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
            {children}
        </th>
    ),
    td: ({ children }) => <td className="border-t border-white/[0.06] px-3 py-2 align-top">{children}</td>,
};

/** Mémoïsé : pendant qu'une réponse arrive, les précédentes ne sont pas réanalysées. */
export const Markdown = memo(function Markdown({ children }: { children: string }) {
    return (
        <div className="min-w-0 text-[15px] text-foreground/90">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {children}
            </ReactMarkdown>
        </div>
    );
});
