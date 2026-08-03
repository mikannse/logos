import type { Metadata } from "next";
import { Outfit, Work_Sans } from "next/font/google";
import "./globals.css";
import NavBar from "@/components/layout/NavBar";

const outfit = Outfit({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-outfit",
});

const workSans = Work_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-work-sans",
});

export const metadata: Metadata = {
  title: "Logos — 给你的好奇心装一张知识地图",
  description: "搜索任意名词，自动构建关系图谱与演化时间轴",
  icons: {
    icon: [
      { url: "/favicon-16.png", sizes: "16x16", type: "image/png" },
      { url: "/icon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/icon-128.png", sizes: "128x128", type: "image/png" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
    shortcut: ["/favicon-16.png"],
  },
  manifest: "/manifest.webmanifest",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="zh-CN"
      className={`${outfit.variable} ${workSans.variable} h-full`}
      suppressHydrationWarning
    >
      <body
        className="min-h-full flex flex-col antialiased grid-backdrop-auto"
        style={{ fontFamily: "var(--font-work-sans)" }}
      >
        <NavBar />
        <main className="flex-1 flex flex-col">{children}</main>
      </body>
    </html>
  );
}
