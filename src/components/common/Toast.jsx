import React from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export default function Toast({ notifications = [], onDismiss }) {
  if (!notifications.length) return null;

  return (
    <div
      className="fixed top-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm pointer-events-none"
      aria-live="polite"
    >
      {notifications.map((n) => {
        const isSuccess = n.type === 'success' || !n.type;
        const isError = n.type === 'error';
        const isWarning = n.type === 'warning';

        return (
          <div
            key={n.id}
            className="pointer-events-auto bg-white border border-[#E2E8F0] shadow-lg rounded-xl p-3.5 flex items-start gap-3 text-sm text-[#0F172A] transform transition-all duration-200 animate-slide-in"
          >
            <div className="flex-shrink-0 mt-0.5">
              {isSuccess && (
                <CheckCircle2 className="w-5 h-5 text-[#16A34A]" />
              )}
              {isError && (
                <AlertCircle className="w-5 h-5 text-[#DC2626]" />
              )}
              {isWarning && (
                <AlertCircle className="w-5 h-5 text-[#D97706]" />
              )}
              {n.type === 'info' && (
                <Info className="w-5 h-5 text-[#2563EB]" />
              )}
            </div>

            <div className="flex-1 font-medium text-xs leading-5">
              {n.message}
            </div>

            {onDismiss && (
              <button
                type="button"
                onClick={() => onDismiss(n.id)}
                className="text-slate-400 hover:text-slate-600 p-0.5 rounded cursor-pointer"
                aria-label="Dismiss toast"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
