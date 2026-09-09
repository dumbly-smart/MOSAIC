'use client';
import React, { useState } from 'react';
import { UploadCloud, FileText, X, CheckCircle2 } from 'lucide-react';

export default function BidderUploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8 animate-in slide-in-from-bottom-4 duration-500">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Bidder Intake Portal</h1>
        <p className="text-slate-500 mt-2">Upload compliance evidence for automated verification.</p>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
        <label className="block text-sm font-semibold text-slate-700 mb-3">Document Package Dropzone</label>
        
        {/* Dynamic Drag & Drop Area */}
        <div 
          className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all duration-200 ${
            isDragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:bg-slate-50'
          }`}
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files) setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
          }}
        >
          <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.docx,.xml" onChange={handleFileChange} className="hidden" id="file-upload" />
          <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center space-y-3">
            <div className={`p-4 rounded-full ${isDragging ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-500'}`}>
              <UploadCloud className="w-8 h-8" />
            </div>
            <div className="text-slate-600 font-medium">
              <span className="text-blue-600 hover:underline">Click to browse</span> or drag and drop
            </div>
            <p className="text-xs text-slate-400">PDF, PNG, JPG, DOCX up to 10MB</p>
          </label>
        </div>

        {/* Dynamic File List */}
        {files.length > 0 && (
          <div className="mt-8 space-y-3">
            <h4 className="text-sm font-bold text-slate-700 flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
              <span>Ready for upload ({files.length})</span>
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {files.map((file, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-200 rounded-lg group">
                  <div className="flex items-center space-x-3 overflow-hidden">
                    <FileText className="w-5 h-5 text-blue-500 flex-shrink-0" />
                    <span className="text-sm font-medium text-slate-700 truncate">{file.name}</span>
                  </div>
                  <button onClick={() => removeFile(idx)} className="text-slate-400 hover:text-red-500 transition-colors p-1">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 pt-6 border-t border-slate-100">
          <button className="w-full py-3.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white font-semibold shadow-md transition-all active:scale-[0.98]">
            Submit Evidence Package
          </button>
        </div>
      </div>
    </div>
  );
}