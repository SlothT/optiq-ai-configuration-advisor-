export function formatUsdCost(amount: number | null | undefined, isLocal?: boolean | null) {
    if (isLocal) {
        return "$0 API charges (local compute excluded)";
    }
    if (amount == null || !Number.isFinite(amount)) return "Unknown cost";
    return `$${amount.toFixed(6)}`;
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
