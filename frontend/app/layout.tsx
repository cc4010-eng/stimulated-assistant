import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stimulated Assistant",
  description: "AI-assisted interviewing and coding for stimulated recall research",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-stone-50 text-stone-900">{children}</body>
    </html>
  );
}
