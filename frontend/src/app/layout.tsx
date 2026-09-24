import type { Metadata } from "next";

import { ChatDrawer } from "@/components/ChatDrawer";
import { Nav } from "@/components/Nav";

import "./globals.css";

export const metadata: Metadata = {
  title: "Incrementality Drift Monitor",
  description: "Know when your incrementality evidence has gone stale.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        <Nav />
        <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 pb-24">{children}</main>
        <ChatDrawer />
      </body>
    </html>
  );
}
