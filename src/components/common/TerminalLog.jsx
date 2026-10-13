import React, { useRef, useEffect, useState } from 'react';
import { Copy, Check, Terminal, Play, Pause } from 'lucide-react';

export default function TerminalLog({
  logs = [],
  isLive = false,
  maxHeight = '420px',
  title = 'Live Agent Stream',
  className = '',
}) {
  const scrollRef = useRef(null);
  const [copied, setCopied] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleCopy = () => {
    const raw = logs
      .map((l) => `[${l.time}] ${l.agent}: ${l.message}`)
      .join('\n');
    navigator.clipboard.writeText(raw);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getAgentColor = (agent) => {
    const upper = String(agent || '').toUpperCase();
    if (upper.includes('ANALYZER')) return 'text-blue-400 bg-blue-950/70 border-blue-800/60';
    if (upper.includes('INVESTIGATOR')) return 'text-amber-400 bg-amber-950/70 border-amber-800/60';
    if (upper.includes('REPAIR') || upper.includes('CODER')) return 'text-emerald-400 bg-emerald-950/70 border-emerald-800/60';
    if (upper.includes('TESTING') || upper.includes('TESTER')) return 'text-emerald-400 bg-emerald-950/70 border-emerald-800/60';
    if (upper.includes('SECURITY')) return 'text-sky-300 bg-sky-950/70 border-sky-800/60';
    return 'text-slate-400 bg-slate-800/60 border-slate-700/60';
  };

  return (
    <div
      className={`rounded-xl border border-slate-800 bg-[#0F172A] shadow-md flex flex-col font-mono text-xs overflow-hidden ${className}`}
    >
      {/* Title Bar */}
      <div className="px-4 py-2.5 bg-[#0B132B] border-b border-slate-800 flex items-center justify-between text-slate-300 select-none">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80 inline-block" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80 inline-block" />
          </div>
          <div className="flex items-center gap-2 pl-2 border-l border-slate-700/60 text-slate-300">
            <Terminal className="w-3.5 h-3.5 text-blue-400" />
            <span className="font-semibold text-xs tracking-tight">{title}</span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          {isLive && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-blue-950/80 border border-blue-700/60 text-blue-400">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
              <span className="font-bold text-[10px] tracking-wider uppercase">Streaming</span>
            </div>
          )}

          <button
            type="button"
            onClick={() => setAutoScroll(!autoScroll)}
            className={`p-1 rounded transition-colors ${
              autoScroll ? 'text-blue-400 hover:text-blue-300' : 'text-slate-500 hover:text-slate-300'
            }`}
            title={autoScroll ? 'Pause auto-scroll' : 'Resume auto-scroll'}
          >
            {autoScroll ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>

          <button
            type="button"
            onClick={handleCopy}
            className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition-colors cursor-pointer text-[11px] font-sans"
            title="Copy logs"
          >
            {copied ? (
              <>
                <Check className="w-3 h-3 text-emerald-400" />
                <span className="text-emerald-400">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3 h-3" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div
        ref={scrollRef}
        className="p-4 overflow-y-auto dark-scroll space-y-2.5 font-mono text-[13px] leading-relaxed text-slate-200 select-text"
        style={{ maxHeight }}
      >
        {logs.length === 0 ? (
          <div className="text-slate-500 italic py-4">Waiting for agent output...</div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} className="flex items-start gap-2.5 hover:bg-slate-800/30 px-1.5 py-0.5 rounded transition-colors">
              <span className="text-slate-500 select-none text-[11px] pt-0.5">
                [{log.time}]
              </span>
              <span
                className={`text-[10px] font-semibold px-1.5 py-0.2 rounded border uppercase tracking-wider flex-shrink-0 select-none ${getAgentColor(
                  log.agent
                )}`}
              >
                {log.agent}
              </span>
              <span className="text-slate-200 flex-1 leading-normal break-words font-mono">
                {log.message}
              </span>
            </div>
          ))
        )}

        {isLive && (
          <div className="flex items-center gap-2 pt-2 text-slate-500 text-xs">
            <span className="w-2 h-4 bg-blue-500 animate-pulse" />
            <span className="text-[11px] text-slate-400">Agents processing task queue...</span>
          </div>
        )}
      </div>
    </div>
  );
}
