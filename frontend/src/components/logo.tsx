export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 font-display font-bold tracking-tight ${className}`}>
      <svg viewBox="0 0 36 36" className="size-9" aria-hidden>
        <rect width="36" height="36" rx="13" className="fill-brand-500" />
        <path d="M10.5 19.2l4.6 4.6L25.5 13" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span className="text-lg">Planit</span>
    </span>
  );
}
