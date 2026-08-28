import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NL-to-Insight BI Copilot",
  description: "A governed five-agent pipeline for safe, evidence-grounded business insight.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
