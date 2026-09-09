'use client';
import React, { useState } from 'react';
import { ShieldAlert, CheckCircle, AlertTriangle, Fingerprint, Banknote, FileCheck } from 'lucide-react';

export default function ResultsPage() {
  const [decision, setDecision] = useState('qualify');

  return (
    <div className="space-y-8 max-w-6xl mx-auto animate-in fade-in duration-500">
      
      {/* Header Panel */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex flex-col md:flex-row justify-between items-center gap-6">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">Case #CAS-2026-0091</h1>
            <span className="bg-blue-100 text-blue-700 text-xs font-bold px-2.5 py-1 rounded-md uppercase tracking-wider">Ready for Review</span>
          </div>
          <p className="text-sm text-slate-500 flex items-center space-x-2">
            <FileCheck className="w-4 h-4" /> <span>Bidder: Apex Infotech | Tender: TND-2026-MECH-04</span>
          </p>
        </div>

        <div className="flex items-center space-x-6 bg-slate-50 px-6 py-3 rounded-xl border border-slate-100">
          <div>
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Compliance Score</div>
            <div className="flex items-end space-x-2">
              <span className="text-3xl font-black text-emerald-600 leading-none">100</span>
              <span className="text-sm font-medium text-slate-500 mb-1">/ 100</span>
            </div>
          </div>
          <div className="h-10 w-px bg-slate-200"></div>
          <div>
            <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">Risk Profile</div>
            <div className="flex items-center space-x-1.5 text-emerald-600">
              <ShieldAlert className="w-5 h-5" />
              <span className="font-bold">Low Risk</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Verification Engine Findings */}
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
            <CheckCircle className="w-5 h-5 text-blue-600" />
            <span>Deterministic Verification Findings</span>
          </h2>
          
          <div className="grid grid-cols-1 gap-4">
            {/* Finding Card 1 */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center space-x-3">
                  <div className="bg-blue-100 p-2 rounded-lg text-blue-600"><Fingerprint className="w-5 h-5" /></div>
                  <h3 className="font-bold text-slate-900">Valid GSTIN Registration</h3>
                </div>
                <span className="bg-emerald-100 text-emerald-700 text-xs font-bold px-2.5 py-1 rounded-md">Verified</span>
              </div>
              <p className="text-sm text-slate-600 mb-4">Document GSTIN matches sandbox portal adapter record. Legal business entity is consistent across uploaded proofs.</p>
              <div className="flex gap-2">
                <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded">GST_Cert.pdf (p.1)</span>
                <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded">Mock GSTN Sandbox</span>
              </div>
            </div>

            {/* Finding Card 2 */}
            <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex justify-between items-start mb-3">
                <div className="flex items-center space-x-3">
                  <div className="bg-purple-100 p-2 rounded-lg text-purple-600"><Banknote className="w-5 h-5" /></div>
                  <h3 className="font-bold text-slate-900">Annual Turnover Threshold</h3>
                </div>
                <span className="bg-emerald-100 text-emerald-700 text-xs font-bold px-2.5 py-1 rounded-md">Verified</span>
              </div>
              <p className="text-sm text-slate-600 mb-4">Audited P&L balance sheet declares turnover exceeding specified limit of 50 Lakhs.</p>
              <div className="flex gap-2">
                <span className="text-xs font-medium bg-slate-100 text-slate-600 px-2 py-1 rounded">CA_Audit.pdf (p.4)</span>
                <span className="text-xs font-medium bg-blue-50 text-blue-600 border border-blue-100 px-2 py-1 rounded">Qwen3-VL: 94% Confidence</span>
              </div>
            </div>
          </div>
        </div>

        {/* Officer Decision Panel */}
        <div className="space-y-6">
          <div className="bg-slate-900 text-white rounded-2xl p-6 shadow-lg relative overflow-hidden">
            <div className="absolute top-0 right-0 p-4 opacity-10"><ShieldAlert className="w-24 h-24" /></div>
            <h3 className="font-bold text-lg mb-2 relative z-10">Officer Authority</h3>
            <p className="text-sm text-slate-300 mb-6 relative z-10">MOSAIC provides grounded evidence. You hold the final authorization.</p>

            <div className="space-y-4 relative z-10">
              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Verdict</label>
                <select
                  value={decision} onChange={(e) => setDecision(e.target.value)}
                  className="w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm font-medium focus:ring-2 focus:ring-blue-500 outline-none"
                >
                  <option value="qualify">Qualify Bidder</option>
                  <option value="disqualify">Disqualify Bidder</option>
                  <option value="request_clarification">Request Clarification</option>
                  <option value="manual_review">Flag for Manual Review</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">Audit Reasoning</label>
                <textarea
                  rows={3} placeholder="Enter statutory justification..."
                  className="w-full p-3 rounded-lg bg-slate-800 border border-slate-700 text-white text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                />
              </div>

              <button className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-lg transition-colors shadow-[0_0_15px_rgba(37,99,235,0.4)]">
                Seal Decision
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}