import Link from "next/link";

const cards = [
    {
        title: "Prompt Analyzer",
        body: "Score prompts, inspect strengths and weaknesses, and estimate cost before running experiments.",
        href: "/prompt-analyzer",
    },
    {
        title: "Experiment Runner",
        body: "Compare live model outputs across prompts, test inputs, and provider configurations.",
        href: "/experiment-runner",
    },
    {
        title: "MLflow Dashboard",
        body: "Review experiment history, metrics, and artifacts from one place.",
        href: "/dashboard",
    },
];

export default function HomePage() {
    return (
        <section className="grid gap-8 lg:grid-cols-[1.3fr_0.7fr]">
            <div className="rounded-[2rem] border border-black/5 bg-white/85 p-8 shadow-panel">
                <p className="text-sm uppercase tracking-[0.24em] text-accent">Phase 0 shell</p>
                <h2 className="mt-3 max-w-2xl text-4xl font-semibold leading-tight">
                    A clean home base for prompt analysis, experiments, and model recommendations.
                </h2>
                <p className="mt-4 max-w-2xl text-base text-ink/70">
                    This scaffold is intentionally small: it gives the backend somewhere to connect and gives
                    the planner&apos;s placeholder routes a visible shape.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                    <Link className="rounded-full bg-ink px-5 py-3 text-sm font-medium text-paper" href="/prompt-analyzer">
                        Open Prompt Analyzer
                    </Link>
                    <Link className="rounded-full border border-black/10 px-5 py-3 text-sm font-medium" href="/settings">
                        Provider Settings
                    </Link>
                </div>
            </div>
            <div className="grid gap-4">
                {cards.map((card) => (
                    <Link
                        key={card.title}
                        href={card.href}
                        className="rounded-[1.75rem] border border-black/5 bg-white/75 p-6 shadow-panel transition hover:-translate-y-0.5 hover:bg-white"
                    >
                        <h3 className="text-lg font-semibold">{card.title}</h3>
                        <p className="mt-2 text-sm text-ink/70">{card.body}</p>
                    </Link>
                ))}
            </div>
        </section>
    );
}
