import React from 'react';
import Badge from '../common/Badge';

export default function RootCause({ rootCause }) {
  const summary = rootCause?.summary || 'authenticateUser is referenced without the required import.';
  const explanation = rootCause?.explanation ||
    'In src/components/Login.jsx, the component imported only login from "./auth". When the user clicks the login button, handleLogin attempts to invoke authenticateUser directly from the global scope, causing an unhandled ReferenceError.';
  const targetModule = rootCause?.file || 'src/components/Login.jsx';

  return (
    <div className="bg-white border border-[#E2E8F0] rounded-xl p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-[#E2E8F0]">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#2563EB]">
            Bug Investigator Finding
          </span>
          <h3 className="text-base font-bold text-[#0F172A] mt-0.5">
            Root Cause Diagnosis
          </h3>
        </div>
        <Badge variant="blue">Confirmed AST Defect</Badge>
      </div>

      <div className="p-4 bg-[#EFF6FF] border border-[#BFDBFE] rounded-xl space-y-2">
        <span className="text-xs font-bold text-[#1E3A8A] block">
          Diagnosis Summary:
        </span>
        <p className="text-sm text-[#1E3A8A] font-medium leading-relaxed">
          "{summary}"
        </p>
      </div>

      <div className="space-y-2 text-xs text-[#64748B] leading-relaxed">
        <p>{explanation}</p>
        <div className="p-3 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-between">
          <span>Target module:</span>
          <strong className="font-mono text-[#0F172A] bg-white px-2 py-0.5 rounded border border-[#E2E8F0]">
            {targetModule}
          </strong>
        </div>
      </div>
    </div>
  );
}
