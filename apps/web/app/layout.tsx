import type { Metadata } from "next";
import { Vazirmatn } from "next/font/google";
import "./globals.css";

const vazir = Vazirmatn({ subsets: ["arabic"], variable: "--font-vazir" });

export const metadata: Metadata = {
  title: "BotForge — سازندهٔ بات تلگرام و بله با هوش مصنوعی",
  description:
    "باتِ کسب‌وکارت را با یک گفت‌وگو بساز، تست کن و منتشر کن؛ رزرو کافه، سفارش منو و پاسخ خودکار به فارسی.",
};

const themeScript = `
try {
  var t = localStorage.getItem("bf-theme");
  if (!t) t = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  document.documentElement.dataset.theme = t;
} catch (e) {}
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" data-theme="dark" className={vazir.variable}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
