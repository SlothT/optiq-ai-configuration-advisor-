import Link from "next/link";

const cards = [
    {
        title: "Model Advisor",
        tag: "Advice before spending",
        body: "Paste a prompt to receive an affordable starting model, explanations, and estimated API costs.",
        href: "/prompt-analyzer",
        action: "Get Advice →",
    },
    {
        title: "Experiment Runner",
        tag: "Multi-Model Benchmarking",
        body: "Optionally compare outputs using your configured providers after reviewing the scope and budget.",
        href: "/experiment-runner",
        action: "Run Experiment →",
    },
    {
        title: "Comparison History",
        tag: "Auditability & Metrics",
        body: "Inspect saved results, costs, failures, and optional tracking records.",
        href: "/dashboard",
        action: "View Dashboard →",
    },
];

const metrics = [
    { label: "Supported Providers", value: "4 (OpenAI, Anthropic, Gemini, Ollama)" },
    { label: "Advice", value: "Local rules · no paid model calls" },
    { label: "Verification", value: "Optional · budget controlled" },
    { label: "Credentials", value: "Encrypted provider keys" },
];

export default function HomePage() {
    return (
        <div className="grid gap-8">
            <section className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
                <div className="rounded-[2rem] border border-black/5 bg-white/90 p-8 shadow-panel">
                    <span className="inline-block rounded-full bg-accent/10 px-3.5 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-accent">
                        Choose before you spend
                    </span>
                    <h2 className="mt-4 max-w-2xl text-4xl font-bold tracking-tight leading-tight">
                        Does your prompt need an expensive model?
                    </h2>
                    <p className="mt-4 max-w-2xl text-base text-ink/70 leading-relaxed">
                        Optiq suggests an affordable LLM for your prompt, explains the trade-offs, and lets you optionally test alternatives. Advice requires no provider keys or dataset.
                    </p>
                    <div className="mt-8 flex flex-wrap items-center gap-3">
                        <Link className="rounded-full bg-ink px-6 py-3.5 text-sm font-semibold text-paper shadow transition hover:bg-ink/90 hover:-translate-y-0.5" href="/prompt-analyzer">
                            Find a Starting Model
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
