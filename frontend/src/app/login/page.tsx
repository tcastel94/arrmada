"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skull, Lock, Loader2 } from "lucide-react";
import { login, isAuthenticated } from "@/lib/api-client";
import { useSetupStatus } from "@/hooks/use-setup";
import { motion } from "framer-motion";

export default function LoginPage() {
    const router = useRouter();
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [loading, setLoading] = useState(false);
    const { data: setupStatus, isLoading: setupLoading } = useSetupStatus();

    useEffect(() => {
        // If not configured, redirect to setup wizard
        if (!setupLoading && setupStatus && !setupStatus.is_configured) {
            router.replace("/setup");
            return;
        }

        if (isAuthenticated()) {
            router.replace("/dashboard");
        }
    }, [router, setupStatus, setupLoading]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");
        setLoading(true);

        try {
            await login(password);
            router.push("/dashboard");
        } catch {
            setError("Mot de passe incorrect");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-background px-4">
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <Card className="w-full max-w-sm">
                    <CardHeader className="text-center space-y-4">
                        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-primary-foreground">
                            <Skull className="h-8 w-8" />
                        </div>
                        <CardTitle className="text-2xl font-bold tracking-tight">
                            ArrMada
                        </CardTitle>
                        <p className="text-sm text-muted-foreground">
                            Entrez votre mot de passe pour accéder au tableau de bord
                        </p>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="relative">
                                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    id="password"
                                    type="password"
                                    placeholder="Mot de passe"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="pl-10"
                                    autoFocus
                                    required
                                />
                            </div>

                            {error && (
                                <p className="text-sm text-destructive text-center">{error}</p>
                            )}

                            <Button
                                type="submit"
                                className="w-full"
                                disabled={loading || !password}
                            >
                                {loading ? (
                                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                                ) : null}
                                Se connecter
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
}
