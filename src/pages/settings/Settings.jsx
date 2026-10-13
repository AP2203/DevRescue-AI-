import React, { useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useApp } from '../../context/AppContext';
import Button, { PrimaryButton } from '../../components/common/Button';
import Card from '../../components/common/Card';
import Badge from '../../components/common/Badge';
import { ConfirmDialog } from '../../components/common/Modal';

// Reusable toggle declared OUTSIDE render to prevent React re-creation warnings
function SettingToggle({ checked, onChange, label, description }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3.5 border-b border-[#E2E8F0]">
      <div>
        <span className="text-sm font-semibold text-[#0F172A] block">
          {label}
        </span>
        {description && (
          <span className="text-xs text-[#64748B] block mt-0.5">
            {description}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={`w-11 h-6 rounded-full transition-colors relative flex items-center px-0.5 cursor-pointer flex-shrink-0 ${
          checked ? 'bg-[#2563EB]' : 'bg-slate-300'
        }`}
      >
        <span
          className={`w-5 h-5 rounded-full bg-white shadow-xs transform transition-transform ${
            checked ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  );
}

export default function Settings() {
  const { user } = useAuth();
  const { resetDemoData } = useApp();

  const [activeTab, setActiveTab] = useState('PROFILE');
  const [resetModalOpen, setResetModalOpen] = useState(false);

  // Settings states
  const [userName, setUserName] = useState(user?.name || 'Ansh');
  const [userEmail, setUserEmail] = useState(user?.email || 'ansh@devrescue.ai');
  const [autoPr, setAutoPr] = useState(false);
  const [requireReview, setRequireReview] = useState(true);
  const [runStressTests, setRunStressTests] = useState(true);
  const [notifyOnComplete, setNotifyOnComplete] = useState(true);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = (e) => {
    e.preventDefault();
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  const handleConfirmReset = () => {
    resetDemoData();
    setResetModalOpen(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Header Bar */}
      <div className="flex items-center justify-between pb-6 border-b border-[#E2E8F0]">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#0F172A]">
            Settings
          </h1>
          <p className="text-sm text-[#64748B] mt-1">
            Maintainer preferences, execution policies, and prototype demo controls.
          </p>
        </div>

        <Badge variant="demo" size="md">
          PROTOTYPE DEMO
        </Badge>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1.5 p-1 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg w-fit">
        {[
          { id: 'PROFILE', label: 'Maintainer Profile' },
          { id: 'POLICIES', label: 'Agent Policies' },
          { id: 'DEMO', label: 'Reset Demo Data' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={`px-3.5 py-1.5 rounded-md text-xs font-semibold transition-all cursor-pointer ${
              activeTab === tab.id
                ? 'bg-white text-[#2563EB] shadow-xs'
                : 'text-[#64748B] hover:text-[#0F172A]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: MAINTAINER PROFILE */}
      {activeTab === 'PROFILE' && (
        <form onSubmit={handleSave} className="space-y-6">
          <Card className="p-6 space-y-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-[#0F172A]">
              Profile Details
            </h3>

            <div>
              <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
                Work Email
              </label>
              <input
                type="email"
                value={userEmail}
                onChange={(e) => setUserEmail(e.target.value)}
                className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1.5">
                GitHub Handle (Demo)
              </label>
              <input
                type="text"
                defaultValue="ansh-dev"
                disabled
                className="w-full rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#64748B] cursor-not-allowed"
              />
            </div>

            <div className="pt-3">
              <PrimaryButton type="submit" size="sm">
                Save Profile
              </PrimaryButton>
              {savedSuccess && (
                <span className="text-xs text-[#16A34A] font-semibold ml-3">
                  ✓ Preferences saved
                </span>
              )}
            </div>
          </Card>
        </form>
      )}

      {/* TAB 2: AGENT POLICIES */}
      {activeTab === 'POLICIES' && (
        <Card className="p-6 space-y-4">
          <h3 className="text-sm font-bold uppercase tracking-wider text-[#0F172A]">
            Autonomous Execution &amp; Dispatch Rules
          </h3>

          <div>
            <SettingToggle
              checked={requireReview}
              onChange={setRequireReview}
              label="Human verification gateway"
              description="Require explicit maintainer approval in the Code Review Desk before pull requests are dispatched."
            />

            <SettingToggle
              checked={runStressTests}
              onChange={setRunStressTests}
              label="Generate regression stress tests"
              description="The Testing Agent will synthesize edge-case concurrent tests to prove invariance."
            />

            <SettingToggle
              checked={autoPr}
              onChange={setAutoPr}
              label="Instant pull request draft on pass"
              description="Automatically create a draft PR in GitHub when 100% tests pass."
            />

            <SettingToggle
              checked={notifyOnComplete}
              onChange={setNotifyOnComplete}
              label="In-app toast notifications on complete"
              description="Display real-time status banners when an agent completes a verification step."
            />
          </div>
        </Card>
      )}

      {/* TAB 3: RESET DEMO DATA (Section 28) */}
      {activeTab === 'DEMO' && (
        <Card className="p-6 space-y-4 border-amber-200 bg-amber-50/20">
          <div className="flex items-start gap-3">
            <div className="w-9 h-9 rounded-lg bg-amber-100 text-[#D97706] flex items-center justify-center flex-shrink-0">
              <RotateCcw className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[#0F172A]">
                Reset Demo Data
              </h3>
              <p className="text-xs text-[#64748B] mt-1 leading-relaxed">
                Restore the prototype's initial mock repositories, investigations, and pull requests. Any custom changes or newly created investigations will be reset to default.
              </p>
            </div>
          </div>

          <div className="pt-4 border-t border-[#E2E8F0]">
            <Button
              variant="danger"
              size="md"
              icon={RotateCcw}
              onClick={() => setResetModalOpen(true)}
            >
              Reset Demo Data
            </Button>
          </div>
        </Card>
      )}

      {/* Section 28 Confirmation Modal */}
      <ConfirmDialog
        isOpen={resetModalOpen}
        onClose={() => setResetModalOpen(false)}
        onConfirm={handleConfirmReset}
        title="Reset Demo Data?"
        description="This will restore the original demonstration state."
        confirmText="Reset"
        cancelText="Cancel"
        danger={true}
      />
    </div>
  );
}
