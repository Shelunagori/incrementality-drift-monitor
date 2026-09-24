import Link from "next/link";

export function Nav() {
  return (
    <nav className="border-b bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3 text-sm">
        <Link href="/" className="font-semibold">
          Drift Monitor
        </Link>
        <Link href="/proposals" className="text-slate-600 hover:text-slate-900">
          Proposals
        </Link>
        <span className="ml-auto text-xs text-slate-400">Synthetic data</span>
      </div>
    </nav>
  );
}
