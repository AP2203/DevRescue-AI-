import React, { useState } from 'react';
import { Copy, Check, FileCode } from 'lucide-react';

export function parseUnifiedDiff(rawDiff) {
  if (!rawDiff || typeof rawDiff !== 'string') return null;
  const rawLines = rawDiff.split('\n');
  const parsed = [];
  let oldLineNum = 1;
  let newLineNum = 1;

  for (const l of rawLines) {
    if (l.startsWith('---') || l.startsWith('+++')) {
      continue;
    }
    if (l.startsWith('@@')) {
      const match = l.match(/@@\s*-(\d+)(?:,\d+)?\s*\+(\d+)(?:,\d+)?\s*@@/);
      if (match) {
        oldLineNum = parseInt(match[1], 10);
        newLineNum = parseInt(match[2], 10);
      }
      continue;
    }

    if (l.startsWith('-')) {
      parsed.push({
        type: 'remove',
        oldLine: oldLineNum++,
        newLine: null,
        text: l
      });
    } else if (l.startsWith('+')) {
      parsed.push({
        type: 'add',
        oldLine: null,
        newLine: newLineNum++,
        text: l
      });
    } else {
      parsed.push({
        type: 'context',
        oldLine: oldLineNum++,
        newLine: newLineNum++,
        text: l.startsWith(' ') ? l : ` ${l}`
      });
    }
  }

  return parsed.length > 0 ? parsed : null;
}

export default function DiffViewer({
  file = 'src/components/Login.jsx',
  diff,
  _originalCode,
  _modifiedCode,
  className = '',
}) {
  const [copied, setCopied] = useState(false);
  const [viewMode, setViewMode] = useState('unified'); // unified | split

  // Extract raw string diff if present
  const rawDiffStr = typeof diff === 'string'
    ? diff
    : (diff?.diff && typeof diff.diff === 'string' ? diff.diff : null);

  const parsedFromText = rawDiffStr ? parseUnifiedDiff(rawDiffStr) : null;

  // Default diff lines if none provided
  const lines = parsedFromText || diff?.lines || [
    { type: 'context', oldLine: 1, newLine: 1, text: "import React, { useState } from 'react';" },
    { type: 'remove', oldLine: 2, newLine: null, text: '- import { login } from "./auth";' },
    { type: 'add', oldLine: null, newLine: 2, text: '+ import { login, authenticateUser } from "./services/authService";' },
    { type: 'context', oldLine: 3, newLine: 3, text: '' },
    { type: 'context', oldLine: 4, newLine: 4, text: 'export function LoginModal({ isOpen, onClose }) {' },
    { type: 'context', oldLine: 5, newLine: 5, text: '  const [email, setEmail] = useState("");' },
    { type: 'context', oldLine: 6, newLine: 6, text: '  const [password, setPassword] = useState("");' },
    { type: 'context', oldLine: 7, newLine: 7, text: '' },
    { type: 'context', oldLine: 8, newLine: 8, text: '  const handleLoginClick = async (e) => {' },
    { type: 'context', oldLine: 9, newLine: 9, text: '    e.preventDefault();' },
    { type: 'context', oldLine: 10, newLine: 10, text: '    await authenticateUser(email, password);' },
    { type: 'context', oldLine: 11, newLine: 11, text: '    onClose();' },
    { type: 'context', oldLine: 12, newLine: 12, text: '  };' },
    { type: 'context', oldLine: 13, newLine: 13, text: '}' },
  ];

  const addedCount = lines.filter((l) => l.type === 'add').length;
  const removedCount = lines.filter((l) => l.type === 'remove').length;

  const handleCopy = () => {
    const raw = lines.map((l) => l.text).join('\n');
    navigator.clipboard.writeText(raw);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border border-slate-800 bg-[#0F172A] shadow-md overflow-hidden font-mono text-xs ${className}`}>
      {/* Diff Toolbar */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#0B132B] border-b border-slate-800 text-slate-300">
        <div className="flex items-center gap-2.5">
          <FileCode className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-slate-200">{file}</span>
          <div className="flex items-center gap-1.5 ml-2">
            <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-semibold text-[11px]">
              +{addedCount}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-rose-950/80 text-rose-400 border border-rose-800/60 font-semibold text-[11px]">
              -{removedCount}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-lg bg-slate-900 p-0.5 border border-slate-700">
            <button
              type="button"
              onClick={() => setViewMode('unified')}
              className={`px-2.5 py-1 rounded text-[11px] font-sans font-medium transition-colors cursor-pointer ${
                viewMode === 'unified'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Unified
            </button>
            <button
              type="button"
              onClick={() => setViewMode('split')}
              className={`px-2.5 py-1 rounded text-[11px] font-sans font-medium transition-colors cursor-pointer ${
                viewMode === 'split'
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Split
            </button>
          </div>

          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer text-[11px] font-sans"
            title="Copy diff to clipboard"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-medium">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Code Area */}
      {viewMode === 'unified' ? (
        <div className="overflow-x-auto dark-scroll max-h-[500px] text-[13px] leading-relaxed select-text py-2">
          {lines.map((line, idx) => {
            const isAdd = line.type === 'add';
            const isRemove = line.type === 'remove';

            return (
              <div
                key={idx}
                className={`flex items-center font-mono py-0.5 px-4 transition-colors ${
                  isAdd
                    ? 'bg-emerald-950/40 text-emerald-300 border-l-2 border-emerald-500'
                    : isRemove
                    ? 'bg-rose-950/40 text-rose-300 border-l-2 border-rose-500'
                    : 'text-slate-300 hover:bg-slate-800/40 border-l-2 border-transparent'
                }`}
              >
                {/* Line numbers */}
                <div className="flex items-center gap-3 w-16 flex-shrink-0 text-slate-600 select-none text-right font-mono text-[11px]">
                  <span className="w-6">
                    {line.oldLine !== null ? line.oldLine : ''}
                  </span>
                  <span className="w-6">
                    {line.newLine !== null ? line.newLine : ''}
                  </span>
                </div>

                {/* Marker */}
                <span
                  className={`w-5 flex-shrink-0 text-center select-none font-bold ${
                    isAdd
                      ? 'text-emerald-400'
                      : isRemove
                      ? 'text-rose-400'
                      : 'text-slate-600'
                  }`}
                >
                  {isAdd ? '+' : isRemove ? '-' : ' '}
                </span>

                {/* Code content */}
                <pre className="flex-1 whitespace-pre overflow-x-visible font-mono">
                  {line.text.replace(/^[+-]\s*/, '')}
                </pre>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="grid grid-cols-2 divide-x divide-slate-800 overflow-x-auto dark-scroll max-h-[500px] text-[13px] leading-relaxed select-text py-2">
          {/* Before Column */}
          <div className="space-y-0.5">
            <div className="px-4 py-1 text-[11px] font-sans font-semibold text-rose-400 bg-rose-950/20 border-b border-slate-800">
              BEFORE
            </div>
            {lines.filter((l) => l.type !== 'add').map((line, idx) => (
              <div
                key={idx}
                className={`flex items-center font-mono py-0.5 px-4 ${
                  line.type === 'remove'
                    ? 'bg-rose-950/40 text-rose-300'
                    : 'text-slate-300'
                }`}
              >
                <span className="w-8 flex-shrink-0 text-slate-600 select-none text-right font-mono text-[11px] pr-2">
                  {line.oldLine || ''}
                </span>
                <span className="w-4 flex-shrink-0 text-rose-400 select-none font-bold">
                  {line.type === 'remove' ? '-' : ' '}
                </span>
                <pre className="flex-1 whitespace-pre overflow-x-visible font-mono">
                  {line.text.replace(/^[+-]\s*/, '')}
                </pre>
              </div>
            ))}
          </div>

          {/* After Column */}
          <div className="space-y-0.5">
            <div className="px-4 py-1 text-[11px] font-sans font-semibold text-emerald-400 bg-emerald-950/20 border-b border-slate-800">
              AFTER
            </div>
            {lines.filter((l) => l.type !== 'remove').map((line, idx) => (
              <div
                key={idx}
                className={`flex items-center font-mono py-0.5 px-4 ${
                  line.type === 'add'
                    ? 'bg-emerald-950/40 text-emerald-300'
                    : 'text-slate-300'
                }`}
              >
                <span className="w-8 flex-shrink-0 text-slate-600 select-none text-right font-mono text-[11px] pr-2">
                  {line.newLine || ''}
                </span>
                <span className="w-4 flex-shrink-0 text-emerald-400 select-none font-bold">
                  {line.type === 'add' ? '+' : ' '}
                </span>
                <pre className="flex-1 whitespace-pre overflow-x-visible font-mono">
                  {line.text.replace(/^[+-]\s*/, '')}
                </pre>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

