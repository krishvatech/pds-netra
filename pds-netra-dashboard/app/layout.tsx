import type { Metadata } from 'next';
import { Sora, Fraunces } from 'next/font/google';
import './globals.css';

export const metadata: Metadata = {
  title: 'PDS Netra Dashboard',
  description: 'Central monitoring dashboard for PDS Netra'
};

const sora = Sora({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap'
});

const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap'
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${sora.variable} ${fraunces.variable} antialiased`} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
