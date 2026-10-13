import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export default function CodeBlock({
  code = '',
  language = 'javascript',
  filename,
  className = '',
  maxHeight = 'max-h-96',
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border border-slate-800 bg-[#0F172A] overflow-hidden shadow-sm font-mono text-xs ${className}`}>
      {(filename || language) && (
        <div className="flex items-center justify-between px-4 py-2.5 bg-[#0B132B] border-b border-slate-800 text-slate-400">
          <span className="font-semibold text-slate-300 text-[11px]">
            {filename || language}
          </span>
          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer text-[11px] font-sans"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      )}
      <div className={`p-4 overflow-x-auto dark-scroll ${maxHeight} text-slate-200 leading-relaxed`}>
        <pre className="font-mono">
          <code>{code}</code>
        </pre>
      </div>
    </div>
  );
}
