import type { Metadata } from 'next';
import { Fraunces, Sora } from 'next/font/google';
import './globals.css';

export const metadata: Metadata = {
  title: 'Digital Netra Auth',
  description: 'Digital Netra authentication portal'
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
