import type { Metadata } from "next";
import { DM_Sans, JetBrains_Mono } from "next/font/google";
import type { ReactNode } from "react";

import { AppProviders } from "@/components/AppProviders";
import Sidebar from "@/components/Sidebar";

import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["300", "400", "500"],
  variable: "--font-sans"
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono"
});

export const metadata: Metadata = {
  title: "DocuMind AI - Document Intelligence Platform",
  description: "Parse, extract, classify, split, and index documents with verifiable AI"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${dmSans.variable} ${jetbrainsMono.variable}`}>
      <head>
        <link
          href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/dist/tabler-icons.min.css"
          rel="stylesheet"
        />
      </head>
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main-content">
            <AppProviders>{children}</AppProviders>
          </main>
        </div>
      </body>
    </html>
  );
}
