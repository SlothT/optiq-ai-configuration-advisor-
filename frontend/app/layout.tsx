import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
    title: "Optiq",
    description: "AI Configuration Advisor",
};

const navItems = [
    { href: "/", label: "Home" },
    { href: "/auth/login", label: "Login" },
    { href: "/auth/register", label: "Register" },
    { href: "/prompt-analyzer", label: "Prompt Analyzer" },
    { href: "/experiment-runner", label: "Experiment Runner" },
    { href: "/recommendations", label: "Recommendations" },
    { href: "/dashboard", label: "Dashboard" },
    { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: Readonly<{ children: any }>) {
    return (
        <html lang="en">
            <body className="min-h-screen bg-paper text-ink antialiased">
                <AppProviders>
                    <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 md:px-8">
                        <header className="mb-8 rounded-3xl border border-black/5 bg-white/85 p-4 shadow-panel backdrop-blur">
                            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <p className="text-xs uppercase tracking-[0.3em] text-accent">Optiq</p>
                                    <h1 className="mt-1 text-2xl font-semibold">AI Configuration Advisor</h1>
                                    <p className="mt-1 max-w-2xl text-sm text-ink/70">
                                        Phase 0 scaffold: backend, frontend shell, model registry, and infrastructure.
                                    </p>
                                </div>
                                <nav className="flex flex-wrap gap-2 text-sm">
                                    {navItems.map((item) => (
                                        <Link
                                            key={item.href}
                                            href={item.href}
                                            className="rounded-full border border-black/10 px-3 py-2 transition hover:border-accent hover:text-accent"
                                        >
                                            {item.label}
                                        </Link>
                                    ))}
                                </nav>
                            </div>
                        </header>
                        <main className="flex-1">{children}</main>
                    </div>
                </AppProviders>
            </body>
        </html>
    );
}
