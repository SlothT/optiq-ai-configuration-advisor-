import Link from "next/link";

const cards = [
    {
        title: "Prompt Analyzer",
        tag: "AI Review",
        body: "Score prompt quality, inspect strengths & weaknesses, compute token counts, and estimate costs across LLM providers.",
        href: "/prompt-analyzer",
        action: "Analyze Prompt →",
    },
    {
        title: "Experiment Runner",
        tag: "Multi-Model Benchmarking",
        body: "Run live side-by-side evaluations across OpenAI, Anthropic, Gemini, and local Ollama models with reference answers.",
        href: "/experiment-runner",
        action: "Run Experiment →",
    },
    {
        title: "MLflow Tracking Dashboard",
        tag: "Auditability & Metrics",
        body: "Inspect experiment metadata, metrics, latency distributions, and artifact records stored securely in MLflow.",
        href: "/dashboard",
        action: "View Dashboard →",
    },
];

const metrics = [
    { label: "Supported Providers", value: "4 (OpenAI, Anthropic, Gemini, Ollama)" },
    { label: "Eval Engine", value: "Ragas + LLM-as-Judge" },
    { label: "Analysis Speed", value: "< 5s p95 latency" },
    { label: "Credentials", value: "AES-256 Fernet Encrypted" },
];

export default function HomePage() {
    return (
        <div className="grid gap-8">
            <section className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
                <div className="rounded-[2rem] border border-black/5 bg-white/90 p-8 shadow-panel">
                    <span className="inline-block rounded-full bg-accent/10 px-3.5 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
                        Pre-Deployment LLM Checkpoint
                    </span>
                    <h2 className="mt-4 max-w-2xl text-4xl font-bold tracking-tight leading-tight">
                        Stop guessing your prompt quality and model choice.
                    </h2>
                    <p className="mt-4 max-w-2xl text-base text-ink/70 leading-relaxed">
                        Optiq actively analyzes prompts, benchmarks models against your hard cost & latency constraints, and recommends the optimal model configuration before production release.
                    </p>
                    <div className="mt-8 flex flex-wrap items-center gap-3">
                        <Link className="rounded-full bg-ink px-6 py-3.5 text-sm font-semibold text-paper shadow transition hover:bg-ink/90 hover:-translate-y-0.5" href="/prompt-analyzer">
                            Start Prompt Analysis
                        </Link>
                        <Link className="rounded-full border border-black/15 bg-white px-6 py-3.5 text-sm font-semibold transition hover:border-accent hover:text-accent hover:-translate-y-0.5" href="/settings">
                            Configure Provider Keys
                        </Link>
                    </div>
                </div>
                <div className="grid gap-4">
                    {cards.map((card) => (
                        <Link
                            key={card.title}
                            href={card.href}
                            className="group rounded-[1.75rem] border border-black/5 bg-white/80 p-6 shadow-panel transition hover:-translate-y-1 hover:border-accent/40 hover:bg-white"
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold uppercase tracking-wider text-accent">{card.tag}</span>
                                <span className="text-sm font-semibold text-ink/40 transition group-hover:text-accent">{card.action}</span>
                            </div>
                            <h3 className="mt-2 text-lg font-bold">{card.title}</h3>
                            <p className="mt-1 text-sm text-ink/70 leading-relaxed">{card.body}</p>
                        </Link>
                    ))}
                </div>
            </section>

            <section className="rounded-[2rem] border border-black/5 bg-white/90 p-6 shadow-panel">
                <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-ink/50 mb-4">Platform Capabilities & Architecture</h3>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {metrics.map((metric) => (
                        <div key={metric.label} className="rounded-2xl border border-black/5 bg-paper/50 p-4">
                            <p className="text-xs text-ink/60 font-medium">{metric.label}</p>
                            <p className="mt-1 text-sm font-bold text-ink">{metric.value}</p>
                        </div>
                    ))}
                </div>
            </section>
        </div>
    );
}
