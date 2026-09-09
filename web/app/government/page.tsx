'use client';
import React, { useState } from 'react';
import { Shield, UploadCloud, FileText, Scale, FileCheck, Trash2, Plus } from 'lucide-react';

export default function GovernmentPage() {
  const [tenderId, setTenderId] = useState('');
  const [title, setTitle] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  
  const [criteriaList, setCriteriaList] = useState([
    { id: 1, clause: 'GSTIN Registration', weight: 30, type: 'identity' },
    { id: 2, clause: 'Annual Turnover > 50L', weight: 40, type: 'financial' },
    { id: 3, clause: 'Non-Debarment Affidavit', weight: 30, type: 'statutory' },
  ]);

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const removeCriterion = (id: number) => {
    setCriteriaList(criteriaList.filter(c => c.id !== id));
  };

  const totalWeight = criteriaList.reduce((sum, item) => sum + item.weight, 0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (totalWeight !== 100) {
      alert('Total weight must equal exactly 100% before publishing.');
      return;
    }
    alert(`Tender ${tenderId} published with an immutable rule-set version!`);
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8 animate-in fade-in duration-500">
      
      {/* Page Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 flex items-center space-x-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <span>Tender Publishing Portal</span>
          </h1>
          <p className="text-slate-500 mt-2 max-w-2xl">
            Upload tender specifications to generate grounded, versioned requirements before bidder scoring begins.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Metadata & Upload */}
        <div className="lg:col-span-1 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 space-y-5">
            <h2 className="font-bold text-slate-900 border-b border-slate-100 pb-2">Tender Details</h2>
            
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Reference ID</label>
              <input
                type="text" required placeholder="e.g., TND-2026-MECH-04"
                value={tenderId} onChange={(e) => setTenderId(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm transition-shadow"
              />
            </div>
            
            <div>
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Procurement Title</label>
              <input
                type="text" required placeholder="Hardware & IT Equipment"
                value={title} onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl border border-slate-300 focus:ring-2 focus:ring-blue-500 focus:outline-none text-sm transition-shadow"
              />
            </div>

            <div className="pt-2">
              <label className="block text-xs font-bold text-slate-500 uppercase tracking-wider mb-2">Rule Set Document</label>
              <div 
                className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all duration-200 ${
                  isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:bg-slate-50'
                }`}
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleFileDrop}
              >
                <input 
                  type="file" accept=".pdf,.docx" className="hidden" id="tender-file" 
                  onChange={(e) => e.target.files && setFile(e.target.files[0])}
                />
                
                {!file ? (
                  <label htmlFor="tender-file" className="cursor-pointer flex flex-col items-center space-y-2">
                    <UploadCloud className={`w-8 h-8 ${isDragging ? 'text-blue-500' : 'text-slate-400'}`} />
                    <div className="text-sm font-medium text-slate-600">
                      <span className="text-blue-600">Browse</span> or drop PDF/DOCX
                    </div>
                  </label>
                ) : (
                  <div className="flex flex-col items-center space-y-2">
                    <FileCheck className="w-8 h-8 text-emerald-500" />
                    <span className="text-sm font-medium text-slate-700 truncate w-full px-2">{file.name}</span>
                    <button type="button" onClick={() => setFile(null)} className="text-xs text-red-500 hover:underline">Remove</button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Rules & Criteria */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 flex flex-col h-full">
            <div className="flex justify-between items-center border-b border-slate-100 pb-4 mb-4">
              <div>
                <h2 className="font-bold text-slate-900 flex items-center space-x-2">
                  <Scale className="w-5 h-5 text-blue-600" />
                  <span>Evaluation Criteria</span>
                </h2>
                <p className="text-xs text-slate-500 mt-1">Weights must equal exactly 100 for automatic scoring.</p>
              </div>
              <div className={`px-3 py-1.5 rounded-lg text-sm font-bold flex items-center space-x-2 ${
                totalWeight === 100 ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
              }`}>
                <span>Total Weight:</span>
                <span className="text-lg">{totalWeight}%</span>
              </div>
            </div>

            <div className="flex-1 space-y-3 overflow-y-auto">
              {criteriaList.map((item, idx) => (
                <div key={item.id} className="flex items-center space-x-4 bg-slate-50 p-4 rounded-xl border border-slate-200 group transition-all hover:border-blue-300">
                  <div className="bg-white border border-slate-200 w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold text-slate-500 shrink-0">
                    {idx + 1}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <input
                      type="text" value={item.clause} readOnly
                      className="w-full bg-transparent text-sm font-semibold text-slate-800 focus:outline-none truncate"
                    />
                    <div className="text-xs text-slate-400 mt-0.5 flex items-center space-x-2">
                      <span className="bg-slate-200 px-2 py-0.5 rounded font-mono uppercase tracking-wider text-[10px] text-slate-600">
                        {item.type}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center space-x-3 shrink-0">
                    <div className="text-sm font-black text-slate-700 bg-white px-3 py-1.5 rounded-lg border border-slate-200 shadow-sm">
                      {item.weight}%
                    </div>
                    <button type="button" onClick={() => removeCriterion(item.id)} className="text-slate-300 hover:text-red-500 transition-colors p-1.5">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
              
              <button type="button" className="w-full py-3 border-2 border-dashed border-slate-200 rounded-xl text-sm font-semibold text-slate-500 hover:text-blue-600 hover:border-blue-300 hover:bg-blue-50 transition-all flex items-center justify-center space-x-2">
                <Plus className="w-4 h-4" />
                <span>Add Grounded Requirement</span>
              </button>
            </div>

            <div className="pt-6 mt-6 border-t border-slate-100">
              <button
                type="submit"
                disabled={totalWeight !== 100}
                className="w-full py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 disabled:bg-slate-300 disabled:cursor-not-allowed text-white font-semibold shadow-md transition-all active:scale-[0.99] flex items-center justify-center space-x-2"
              >
                <FileText className="w-5 h-5" />
                <span>Publish Immutable Rule Set</span>
              </button>
            </div>
          </div>
        </div>

      </form>
    </div>
  );
}