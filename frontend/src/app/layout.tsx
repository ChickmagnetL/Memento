import type { Metadata } from "next";
import { Geist, Geist_Mono, Kalam } from "next/font/google";
import { Sidebar } from "@/components/layout/sidebar";
import { ChatStoreProvider } from "@/lib/chat-store";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const brandFont = Kalam({
  variable: "--font-brand",
  subsets: ["latin"],
  weight: "700",
});

export const metadata: Metadata = {
  title: "Memento",
  description: "Video knowledge base assistant",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${brandFont.variable} h-full antialiased`}
    >
      <body className="h-full flex bg-background text-foreground">
        <Sidebar />
        <main className="relative min-w-0 flex-1 overflow-y-auto">
          <div className="desktop-drag-region" aria-hidden="true" />
          <ChatStoreProvider>{children}</ChatStoreProvider>
        </main>
      </body>
    </html>
  );
}
