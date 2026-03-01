"use client";

import { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { SERVICE_META } from "@/lib/constants";
import type { ServiceType } from "@/types";
import type { ArrService, CreateServicePayload } from "@/types/service";

interface ServiceConfigDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (data: CreateServicePayload) => void;
    service?: ArrService | null;
    isLoading?: boolean;
}

export function ServiceConfigDialog({
    open,
    onOpenChange,
    onSubmit,
    service,
    isLoading,
}: ServiceConfigDialogProps) {
    const isEditing = !!service;

    const [name, setName] = useState(service?.name || "");
    const [type, setType] = useState<ServiceType>(service?.type || "sonarr");
    const [url, setUrl] = useState(service?.url || "");
    const [apiKey, setApiKey] = useState("");
    const [isEnabled, setIsEnabled] = useState(service?.is_enabled ?? true);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        onSubmit({
            name,
            type,
            url,
            api_key: apiKey,
            is_enabled: isEnabled,
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>
                        {isEditing ? "Modifier le service" : "Ajouter un service"}
                    </DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="service-name">Nom</Label>
                        <Input
                            id="service-name"
                            placeholder="Mon Sonarr"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="service-type">Type</Label>
                        <Select
                            value={type}
                            onValueChange={(v) => setType(v as ServiceType)}
                            disabled={isEditing}
                        >
                            <SelectTrigger id="service-type">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                {Object.entries(SERVICE_META).map(([key, meta]) => (
                                    <SelectItem key={key} value={key}>
                                        {meta.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="service-url">URL</Label>
                        <Input
                            id="service-url"
                            placeholder="http://192.168.1.100:8989"
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="service-api-key">
                            Clé API {isEditing && "(laisser vide pour ne pas changer)"}
                        </Label>
                        <Input
                            id="service-api-key"
                            type="password"
                            placeholder="••••••••"
                            value={apiKey}
                            onChange={(e) => setApiKey(e.target.value)}
                            required={!isEditing}
                        />
                    </div>

                    <div className="flex items-center justify-between">
                        <Label htmlFor="service-enabled">Activé</Label>
                        <Switch
                            id="service-enabled"
                            checked={isEnabled}
                            onCheckedChange={setIsEnabled}
                        />
                    </div>

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Annuler
                        </Button>
                        <Button type="submit" disabled={isLoading}>
                            {isLoading
                                ? "En cours..."
                                : isEditing
                                    ? "Modifier"
                                    : "Ajouter"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
