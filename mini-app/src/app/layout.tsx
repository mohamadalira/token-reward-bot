import type { Metadata, Viewport } from 'next';
import './globals.css';
import { TelegramProvider } from '@/lib/telegram';
import Script from 'next/script';

export const metadata: Metadata = {
  title: 'ربات توکن',
  description: 'کسب توکن و خرید کانفیگ VPN',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <head>
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
      </head>
      <body className="font-vazir min-h-screen antialiased">
        <TelegramProvider>{children}</TelegramProvider>
      </body>
    </html>
  );
}
