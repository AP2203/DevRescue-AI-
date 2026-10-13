import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { History, PlusCircle } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/Badge';
import { SearchInput } from '../../components/common/FormInputs';
import EmptyState from '../../components/common/EmptyState';

export default function InvestigationHistory() {
  const { investigations } = useApp();
  const [search, setSearch] = useState('');

  const filtered = investigations.filter((inv) => {
    const q = search.toLowerCase();
    return (
      inv.repo.toLowerCase().includes(q) ||
      (inv.title && inv.title.toLowerCase().includes(q)) ||
      (inv.issueTitle && inv.issueTitle.toLowerCase().includes(q)) ||
      String(inv.number).includes(q) ||
      String(inv.issueNumber).includes(q)
    );
  });

  return (
    <div className="space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-[#E2E8F0]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            Investigation History
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            Complete archive of autonomous bug repair orders and dossiers.
          </p>
        </div>

        <PrimaryButton
          to="/investigations/new"
          icon={PlusCircle}
          size="sm"
        >
          New Investigation
        </PrimaryButton>
      </div>

      {/* Search Toolbar */}
      <div className="w-full sm:w-80">
        <SearchInput
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search investigations by repo or issue..."
        />
      </div>

      {/* History List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={History}
          title="No investigations found"
          description={
            search
              ? `No investigations matching "${search}".`
              : 'Launch your first AI investigation order.'
          }
          actionLabel="New Investigation"
          actionTo="/investigations/new"
        />
      ) : (
        <div className="bg-white border border-[#E2E8F0] rounded-xl overflow-hidden shadow-xs">
          <div className="divide-y divide-[#E2E8F0]">
            {filtered.map((inv) => (
              <div
                key={inv.id}
                className="p-5 hover:bg-[#F8FAFC] transition-colors flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2.5">
                    <span className="font-mono text-xs font-bold text-[#2563EB] bg-[#EFF6FF] px-2 py-0.5 rounded border border-[#BFDBFE]">
                      #{inv.number}
                    </span>
                    <Link
                      to={`/investigations/${inv.id}`}
                      className="text-sm font-bold text-[#0F172A] hover:text-[#2563EB] truncate"
                    >
                      {inv.title || inv.issueTitle}
                    </Link>
                  </div>

                  <div className="flex flex-wrap items-center gap-2.5 text-xs text-[#64748B]">
                    <span className="font-mono text-[#0F172A] font-medium">{inv.repo}</span>
                    <span>·</span>
                    <span className="font-mono text-slate-500">branch: {inv.branch || 'main'}</span>
                    <span>·</span>
                    <span>{inv.startedAt || 'Today'}</span>
                    {inv.testSummary && (
                      <>
                        <span>·</span>
                        <span className="text-[#16A34A] font-medium">
                          {inv.testSummary.passed}/{inv.testSummary.total} tests green
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-3 flex-shrink-0">
                  <StatusBadge status={inv.status} />

                  <div className="flex items-center gap-2">
                    <Button
                      to={`/investigations/${inv.id}`}
                      variant="outline"
                      size="sm"
                    >
                      War Room
                    </Button>
                    <Button
                      to={`/investigations/${inv.id}/review`}
                      variant="primary"
                      size="sm"
                    >
                      Review Fix
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
