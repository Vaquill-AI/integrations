import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Vaquill Legal Assistant",
  description: "AI-powered legal research assistant — powered by Vaquill",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const theme =
    (process.env.NEXT_PUBLIC_THEME as "dark" | "light" | undefined) ?? "dark";

  return (
    <html lang="en" data-theme={theme}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
