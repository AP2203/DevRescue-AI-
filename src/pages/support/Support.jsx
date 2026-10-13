import React, { useState } from 'react';
import { ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import { PrimaryButton } from '../../components/common/Button';
import Badge from '../../components/common/Badge';

const FAQS = [
  {
    q: 'How does DevRescue AI prevent regressions in existing code?',
    a: 'Every synthesized patch must pass two verification hurdles: first, all existing test suites must pass 100% green without modification; second, the Testing Agent synthesizes new regression stress tests targeting the specific failure condition.',
  },
  {
    q: 'Are our repository tokens or code permanently stored?',
    a: 'No. Repositories are cloned into single-use ephemeral container sandboxes that are destroyed immediately upon task completion. In this frontend prototype, all data is simulated in local state.',
  },
  {
    q: 'What occurs when an issue cannot be reproduced inside the sandbox?',
    a: 'If the Bug Investigator cannot reproduce the failure within sandbox bounds, the investigation is marked as requiring human review and detailed diagnostic telemetry is provided.',
  },
  {
    q: 'How does the human-in-the-loop review work?',
    a: 'Maintainers inspect line diffs, test logs, and security results in the Code Review Desk. No pull request is drafted without explicit approval.',
  },
];

export default function Support() {
  const [openFaq, setOpenFaq] = useState(0);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setSubmitted(true);
    setTimeout(() => {
      setName('');
      setEmail('');
      setMessage('');
      setSubmitted(false);
    }, 4000);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-20 space-y-12">
      {/* Title */}
      <div className="pb-6 border-b border-[#E2E8F0] space-y-3">
        <Badge variant="blue" size="sm">
          DEVELOPER SUPPORT
        </Badge>
        <h1 className="text-3xl sm:text-4xl font-extrabold text-[#0F172A] tracking-tight">
          Help &amp; Developer Support
        </h1>
        <p className="text-sm text-[#64748B] max-w-2xl leading-relaxed">
          Frequently asked questions regarding our autonomous bug repair pipeline, test verification, and prototype environment.
        </p>
      </div>

      {/* FAQ Accordion */}
      <div className="space-y-3">
        <h2 className="text-lg font-bold text-[#0F172A] mb-4">Frequently Asked Questions</h2>
        {FAQS.map((faq, idx) => {
          const isOpen = openFaq === idx;
          return (
            <div
              key={idx}
              className={`rounded-xl border transition-all ${
                isOpen ? 'bg-white border-[#2563EB] shadow-xs' : 'bg-white border-[#E2E8F0]'
              }`}
            >
              <button
                type="button"
                onClick={() => setOpenFaq(isOpen ? null : idx)}
                className="w-full flex items-center justify-between text-left p-4 sm:p-5 gap-4 cursor-pointer"
              >
                <span className="text-sm font-bold text-[#0F172A]">{faq.q}</span>
                {isOpen ? (
                  <ChevronUp className="w-4 h-4 text-[#2563EB] flex-shrink-0" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-[#64748B] flex-shrink-0" />
                )}
              </button>

              {isOpen && (
                <div className="px-4 sm:px-5 pb-5 pt-1 text-xs text-[#64748B] leading-relaxed border-t border-[#E2E8F0]">
                  {faq.a}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Contact Form */}
      <div className="bg-white border border-[#E2E8F0] rounded-2xl p-6 sm:p-8 space-y-4 shadow-sm">
        <div>
          <h3 className="text-lg font-bold text-[#0F172A]">Send an Inquiry</h3>
          <p className="text-xs text-[#64748B] mt-0.5">
            Contact the engineering team regarding custom configurations.
          </p>
        </div>

        {submitted ? (
          <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs text-[#16A34A] flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            <span>Thank you! Your simulated inquiry has been recorded.</span>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1">
                  Your Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Ansh"
                  required
                  className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1">
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ansh@devrescue.ai"
                  required
                  className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-[#0F172A] uppercase tracking-wider mb-1">
                Question or Message
              </label>
              <textarea
                rows={4}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Ask about agent capabilities, custom language parsers, or testing frameworks..."
                required
                className="w-full rounded-lg bg-white border border-[#E2E8F0] px-3.5 py-2 text-sm text-[#0F172A] focus:outline-none focus:ring-2 focus:ring-[#2563EB]/20 focus:border-[#2563EB]"
              />
            </div>

            <PrimaryButton type="submit" size="md">
              Send Message
            </PrimaryButton>
          </form>
        )}
      </div>
    </div>
  );
}
