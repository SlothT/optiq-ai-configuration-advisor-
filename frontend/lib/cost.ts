export function formatUsdCost(amount: number, isLocal?: boolean | null) {
    if (isLocal) {
        return "Free (local)";
    }
    return `$${Number(amount || 0).toFixed(4)}`;
}

export function analysisModeLabel(mode: unknown) {
    if (mode === "live") {
        return "Live judge";
    }
    if (mode === "fallback") {
        return "Rule-based fallback (judge unavailable)";
    }
    return String(mode || "unknown");
}
