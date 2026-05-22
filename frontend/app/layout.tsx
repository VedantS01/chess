import "./globals.css";
import type { Metadata } from "next";
import { ReactNode } from "react";

export const metadata: Metadata = {
  title: "chesslab",
  description:
    "Chess engine + bot framework + RL training + online play with ELO ladder.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="border-b border-neutral-800 px-6 py-3 flex gap-6 text-sm">
          <a href="/" className="font-semibold">
            chesslab
          </a>
          <a href="/play">play</a>
          <a href="/bots">bots</a>
          <a href="/leaderboard">leaderboard</a>
        </nav>
        <main className="px-6 py-6 max-w-5xl mx-auto">{children}</main>
      </body>
    </html>
  );
}
