import React from 'react';
import { Bug, Home, LayoutDashboard } from 'lucide-react';
import Button, { PrimaryButton } from '../../components/common/Button';

export default function NotFound() {
  return (
    <div className="min-h-[75vh] flex flex-col items-center justify-center text-center px-4 py-16">
      <div className="w-14 h-14 rounded-2xl bg-[#EFF6FF] text-[#2563EB] border border-[#BFDBFE] flex items-center justify-center mb-6 shadow-xs">
        <Bug className="w-7 h-7" />
      </div>

      <span className="text-xs font-mono font-bold text-[#2563EB] uppercase tracking-wider bg-[#EFF6FF] px-3 py-1 rounded-full border border-[#BFDBFE] mb-3">
        404 ERROR
      </span>

      <h1 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight mb-2">
        Page not found
      </h1>

      <p className="text-sm text-[#64748B] max-w-sm mb-8 leading-relaxed">
        The route you requested does not exist or has been relocated in the DevRescue AI platform.
      </p>

      <div className="flex flex-col sm:flex-row items-center gap-3">
        <PrimaryButton
          to="/dashboard"
          icon={LayoutDashboard}
          size="md"
        >
          Back to Dashboard
        </PrimaryButton>

        <Button
          to="/"
          variant="outline"
          icon={Home}
          size="md"
        >
          Go to Home
        </Button>
      </div>
    </div>
  );
}
