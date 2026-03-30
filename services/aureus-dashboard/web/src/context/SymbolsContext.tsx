"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface SymbolData {
    name: string;
    digits: number;
    description?: string;
}

type SymbolApiItem = string | Partial<SymbolData>;

interface SymbolsContextType {
    symbols: SymbolData[];
    loading: boolean;
    error: string | null;
    refreshSymbols: () => Promise<void>;
}

const SymbolsContext = createContext<SymbolsContextType | undefined>(undefined);

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

export const SymbolsProvider = ({ children }: { children: ReactNode }) => {
    const [symbols, setSymbols] = useState<SymbolData[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    const fetchSymbols = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}/symbols`);
            if (!res.ok) throw new Error("Failed to fetch symbols");
            const data = (await res.json()) as SymbolApiItem[];

            // Normalize: API returns objects {name, ...} or plain strings
            const normalized: SymbolData[] = data.map((s) => {
                if (typeof s === 'string') {
                    return { name: s, digits: 2 }; // Default digits if missing
                }
                return {
                    name: s.name ?? 'UNKNOWN',
                    digits: s.digits ?? 2,
                    description: s.description
                };
            });

            setSymbols(normalized);
            setError(null);
        } catch (err: unknown) {
            console.error("SymbolsContext fetch error:", err);
            setError(err instanceof Error ? err.message : "Failed to fetch symbols");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchSymbols();
    }, []);

    return (
        <SymbolsContext.Provider value={{ symbols, loading, error, refreshSymbols: fetchSymbols }}>
            {children}
        </SymbolsContext.Provider>
    );
};

export const useSymbols = () => {
    const context = useContext(SymbolsContext);
    if (context === undefined) {
        throw new Error('useSymbols must be used within a SymbolsProvider');
    }
    return context;
};
