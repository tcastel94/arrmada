"use client"

import * as React from "react"
import * as DialogPrimitive from "@radix-ui/react-dialog"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Fenêtre modale.
 * ----------------------------------------------------------------
 * - Mobile : « feuille » qui monte du bas de l'écran, coins arrondis en
 *   haut et poignée grise, comme les feuilles iOS. Le contenu défile à
 *   l'intérieur et respecte la barre d'accueil de l'iPhone (safe area).
 * - Écran large (≥ 640 px) : fenêtre centrée classique qui apparaît en
 *   fondu avec un très léger zoom.
 * Même composant pour les deux : chaque écran garde un seul code.
 */
const Dialog = DialogPrimitive.Root

const DialogTrigger = DialogPrimitive.Trigger

const DialogPortal = DialogPrimitive.Portal

const DialogClose = DialogPrimitive.Close

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/60 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className
    )}
    {...props}
  />
))
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        // Base commune
        "fixed z-50 grid w-full gap-4 overflow-y-auto overscroll-contain bg-popover p-5 text-popover-foreground outline-none",
        "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=open]:duration-300 data-[state=closed]:duration-200 data-[state=open]:ease-smooth",
        // Mobile : feuille du bas
        "inset-x-0 bottom-0 max-h-[92dvh] rounded-t-[22px] pb-[calc(1.25rem+env(safe-area-inset-bottom))] pt-7",
        "data-[state=open]:slide-in-from-bottom data-[state=closed]:slide-out-to-bottom",
        // Écran large : fenêtre centrée
        "sm:inset-auto sm:left-1/2 sm:top-1/2 sm:max-h-[88dvh] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl sm:border sm:border-white/[0.08] sm:p-6 sm:shadow-[0_24px_80px_-12px_rgb(0_0_0/0.8)]",
        "sm:data-[state=open]:fade-in-0 sm:data-[state=open]:zoom-in-[0.97] sm:data-[state=open]:slide-in-from-left-1/2 sm:data-[state=open]:slide-in-from-top-[48%]",
        "sm:data-[state=closed]:fade-out-0 sm:data-[state=closed]:zoom-out-[0.97] sm:data-[state=closed]:slide-out-to-left-1/2 sm:data-[state=closed]:slide-out-to-top-[48%]",
        className
      )}
      {...props}
    >
      {/* Poignée de la feuille (mobile) */}
      <span aria-hidden className="absolute left-1/2 top-2 h-[5px] w-9 -translate-x-1/2 rounded-full bg-white/25 sm:hidden" />
      {children}
      <DialogPrimitive.Close className="absolute right-3.5 top-3.5 flex h-7 w-7 items-center justify-center rounded-full bg-white/[0.1] text-foreground/70 transition-colors hover:bg-white/[0.16] hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none">
        <X className="h-3.5 w-3.5" strokeWidth={2.5} />
        <span className="sr-only">Fermer</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
))
DialogContent.displayName = DialogPrimitive.Content.displayName

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-1 pr-8 text-left",
      className
    )}
    {...props}
  />
)
DialogHeader.displayName = "DialogHeader"

const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
      className
    )}
    {...props}
  />
)
DialogFooter.displayName = "DialogFooter"

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      "text-[19px] font-semibold leading-tight tracking-tight",
      className
    )}
    {...props}
  />
))
DialogTitle.displayName = DialogPrimitive.Title.displayName

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn("text-[14px] text-muted-foreground", className)}
    {...props}
  />
))
DialogDescription.displayName = DialogPrimitive.Description.displayName

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogTrigger,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
}
