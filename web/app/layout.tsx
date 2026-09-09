import type { Metadata } from 'next';
import Link from 'next/link';
import './globals.css';

export const metadata: Metadata = {
  title: 'MOSAIC | Procurement Decision Support',
  description: 'Multi-portal Officer-led Statutory Assessment and Integrated Compliance',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
        <header className="bg-slate-900 border-b border-slate-800 text-white sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="h-8 w-8 rounded bg-blue-600 flex items-center justify-center font-bold text-white text-lg">M</div>
              <span className="font-semibold text-lg tracking-tight">MOSAIC Portal</span>
            </div>
            <nav className="flex space-x-6 text-sm font-medium">
              <Link href="/government" className="text-slate-300 hover:text-white transition">Gov Requirements</Link>
              <Link href="/bidder" className="text-slate-300 hover:text-white transition">Bidder Upload</Link>
              <Link href="/results" className="text-slate-300 hover:text-white transition">Compliance Review</Link>
            </nav>
          </div>
        </header>
        <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-10">
          {children}
        </main>
      </body>
    </html>
  );
}