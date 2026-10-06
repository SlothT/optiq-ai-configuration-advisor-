import type { ReactNode } from "react";

export function AdvancedSettings({ children, active = false, title = "Advanced settings" }: {
  children: ReactNode;
  active?: boolean;
  title?: string;
}) {
  return (
    <details className="rounded-2xl border border-black/10 p-4">
      <summary className="cursor-pointer text-sm font-medium">
        {title}{active ? " · Custom settings active" : ""}
      </summary>
      <div className="mt-4 grid gap-4">{children}</div>
    </details>
  );
}
