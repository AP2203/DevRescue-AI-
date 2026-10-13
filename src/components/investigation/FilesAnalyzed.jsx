import React from 'react';
import { FileCode } from 'lucide-react';

export default function FilesAnalyzed({ files = [] }) {
  const displayFiles = files.length > 0 ? files : ['src/components/Login.jsx', 'src/services/authService.js'];

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
        <div>
          <h3 className="text-sm font-bold text-[#0F172A]">
            Files Analyzed &amp; Modulated by AI
          </h3>
          <p className="text-xs text-[#64748B] mt-0.5">
            The Repository Analyzer traced AST cross-references to these modules:
          </p>
        </div>
        <span className="text-xs font-mono font-semibold text-[#2563EB] bg-[#EFF6FF] px-2.5 py-0.5 rounded border border-[#BFDBFE]">
          {displayFiles.length} files
        </span>
      </div>

      <div className="space-y-3">
        {displayFiles.map((file) => (
          <div
            key={file}
            className="p-4 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] flex items-center justify-between text-xs hover:border-[#CBD5E1] transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-white border border-[#E2E8F0] flex items-center justify-center text-[#2563EB]">
                <FileCode className="w-4 h-4" />
              </div>
              <div>
                <span className="font-mono font-bold text-[#0F172A] block">{file}</span>
                <span className="text-[11px] text-[#64748B] block mt-0.5">AST parsed · Symbol dependencies indexed</span>
              </div>
            </div>
            <span className="text-xs font-semibold text-[#16A34A] bg-[#DCFCE7] px-2.5 py-0.5 rounded-full">
              In Scope
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
