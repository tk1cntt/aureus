"use client";

import { useEffect, useState, ReactNode } from "react";

interface ClientOnlyProps {
    children: ReactNode;
}

/**
 * Wrapper component to ensure children are only rendered on the client.
 * This prevents React hydration mismatches caused by browser extensions 
 * (like Bitdefender chosing bis_skin_checked attributes).
 */
export default function ClientOnly({ children }: ClientOnlyProps) {
    const [hasMounted, setHasMounted] = useState(false);

    useEffect(() => {
        setHasMounted(true);
    }, []);

    if (!hasMounted) {
        return null; // Or a loading skeleton if preferred
    }

    return <>{children}</>;
}
