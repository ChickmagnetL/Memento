import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { getHealth } from "@/lib/api";
import { Sidebar } from "@/components/layout/sidebar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Memento",
  description: "Video knowledge base assistant",
};

async function fetchHealth(): Promise<string> {
  try {
    const data = await getHealth();
    return data.status;
  } catch {
    return "unreachable";
  }
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const health = await fetchHealth();

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex bg-background text-foreground">
        <Sidebar health={health} />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </body>
    </html>
  );
}
