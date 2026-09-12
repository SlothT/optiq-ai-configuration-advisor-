import type { Metadata } from "next";
import Link from "next/link";
import { BrandMark } from "@/components/BrandMark";
import { HeaderAuth } from "@/components/HeaderAuth";
import "./globals.css";
import { AppProviders } from "./providers";

export const metadata: Metadata = {
    title: "Optiq",
    description: "AI Configuration Advisor",
};

const navItems = [
    { href: "/", label: "Overview" },
    { href: "/prompt-analyzer", label: "Prompt Analyzer" },
    { href: "/experiment-runner", label: "Experiment Runner" },
    { href: "/recommendations", label: "Recommendations" },
    { href: "/dashboard", label: "MLflow" },
    { href: "/settings", label: "Settings" },
];

export default function RootLayout({ children }: Readonly<{ children: any }>) {
    return (
        <html lang="en">
            <body className="min-h-screen bg-paper text-ink antialiased">
                <AppProviders>
                    <div className="mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 md:px-8">
                        <header className="mb-8 rounded-3xl border border-black/5 bg-white/90 px-5 py-4 shadow-panel backdrop-blur">
                            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                <Link href="/" className="inline-flex items-center">
                                    <BrandMark />
                                </Link>
                                <div className="flex flex-col items-end gap-3">
                                    <HeaderAuth />
                                    <nav className="flex flex-wrap justify-end gap-1.5 text-sm">
                                        {navItems.map((item) => (
                                            <Link
                                                key={item.href}
                                                href={item.href}
                                                className="rounded-full border border-black/10 bg-white/50 px-3.5 py-1.5 transition hover:border-accent hover:text-accent font-medium"
                                            >
                                                {item.label}
                                            </Link>
                                        ))}
                                    </nav>
                                </div>
                            </div>
                        </header>
                        <main className="flex-1">{children}</main>
                    </div>
                </AppProviders>
            </body>
        </html>
    );
}
