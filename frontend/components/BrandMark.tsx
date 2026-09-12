export function BrandMark() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-2xl bg-ink text-sm font-bold text-paper">
        O
        <span className="absolute bottom-1 right-1 h-2.5 w-2.5 rounded-[5px] bg-accent" aria-hidden />
      </span>
      <span className="text-xl font-bold tracking-tight">Optiq</span>
    </span>
  );
}
