import Link from 'next/link';
import { ShieldCheck, FileSearch, ArrowRight } from 'lucide-react';

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] text-center space-y-10 animate-in fade-in duration-700">
      <div className="space-y-4 max-w-3xl">
        <div className="inline-flex items-center space-x-2 bg-blue-50 text-blue-700 px-4 py-1.5 rounded-full text-sm font-semibold mb-4 border border-blue-100">
          <ShieldCheck className="w-4 h-4" />
          <span>Decision Support System</span>
        </div>
        <h1 className="text-5xl md:text-6xl font-extrabold text-slate-900 tracking-tight">
          Automated Compliance <br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-emerald-600">
            Verification
          </span>
        </h1>
        <p className="text-lg text-slate-600 max-w-2xl mx-auto leading-relaxed">
          MOSAIC cross-references bidder documents with statutory requirements using AI and deterministic rule engines to support procurement officers.
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 w-full justify-center max-w-md">
        <Link href="/government" className="group flex items-center justify-center space-x-2 bg-slate-900 hover:bg-slate-800 text-white px-8 py-3.5 rounded-xl font-medium transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5">
          <span>Publish Tender</span>
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </Link>
        <Link href="/bidder" className="group flex items-center justify-center space-x-2 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 px-8 py-3.5 rounded-xl font-medium transition-all shadow-sm hover:shadow-md">
          <FileSearch className="w-4 h-4 text-slate-400 group-hover:text-blue-500 transition-colors" />
          <span>Submit Evidence</span>
        </Link>
      </div>
    </div>
  );
}