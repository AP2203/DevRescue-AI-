import React, { useState, useEffect } from 'react';
import { DollarSign, ShieldCheck, Zap, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, Lock } from 'lucide-react';
import api from '../../services/api';

export default function PayPalBountyCard({
  repository,
  issueNumber,
  issueTitle,
  errorDescription,
  onBountyFunded,
  fundedOrder = null
}) {
  const [loading, setLoading] = useState(false);
  const [quote, setQuote] = useState(null);
  const [showBreakdown, setShowBreakdown] = useState(false);
  const [error, setError] = useState(null);
  const [paypalConfig, setPaypalConfig] = useState(null);
  const [processingPayment, setProcessingPayment] = useState(false);
  const [activeOrder, setActiveOrder] = useState(fundedOrder);

  // 1. Fetch PayPal config and dynamic bounty quote when issue/error changes
  useEffect(() => {
    let isMounted = true;

    async function loadConfigAndQuote() {
      try {
        setLoading(true);
        setError(null);

        // Fetch public PayPal config
        try {
          const config = await api.getPayPalConfig();
          if (isMounted) setPaypalConfig(config);
        } catch (e) {
          console.warn("PayPal config fallback:", e);
        }

        // Fetch AI dynamic quote based on issue & stacktrace
        const quotedData = await api.quotePayPalBounty({
          repository: repository || 'custom-repository',
          issue_number: issueNumber ? parseInt(issueNumber, 10) : 42,
          issue_title: issueTitle || 'Bug Investigation',
          error_description: errorDescription || '',
          cyclomatic_complexity: 2.5,
          files_expected: 1,
          test_count: 5
        });

        if (isMounted) {
          setQuote(quotedData);
        }
      } catch (err) {
        console.error("Failed to load quote:", err);
        if (isMounted) {
          setError("Could not generate dynamic quote. Defaulting to standard baseline.");
          setQuote({
            bounty_amount: 25.0,
            currency: 'USD',
            risk_tier: 'LOW',
            complexity_score: 3.0,
            breakdown: { base_fee: 15.0, complexity_fee: 5.0, sandbox_compute_fee: 5.0 },
            recommendation: "Allocating standard 5-agent pipeline with PayPal verification escrow."
          });
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadConfigAndQuote();
    return () => { isMounted = false; };
  }, [repository, issueNumber, issueTitle, errorDescription]);

  // Handle funding the bounty via PayPal Sandbox
  const handleFundWithPayPal = async () => {
    if (!quote) return;
    try {
      setProcessingPayment(true);
      setError(null);

      // Create order on PayPal sandbox
      const order = await api.createPayPalOrder({
        amount: quote.bounty_amount,
        currency: quote.currency || 'USD',
        repository: repository || 'custom-repository',
        issue_number: issueNumber ? parseInt(issueNumber, 10) : 42,
        issue_title: issueTitle || 'Bug Investigation',
        description: `DevRescue AI Bounty for ${repository} #${issueNumber}`
      });

      setActiveOrder(order);
      if (onBountyFunded) {
        onBountyFunded(order);
      }
    } catch (err) {
      console.error("PayPal order creation failed:", err);
      setError("Payment authorization failed. Please check sandbox credentials.");
    } finally {
      setProcessingPayment(false);
    }
  };

  const getTierBadge = (tier) => {
    if (tier === 'HIGH') return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
    if (tier === 'MEDIUM') return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
    return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-cyan-500/30 bg-[#0c1017] p-5 shadow-lg shadow-cyan-950/20">
      {/* Top Banner */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-800">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <DollarSign className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h3 className="text-base font-semibold text-white">PayPal Autonomous Bug Bounty</h3>
              <span className="px-2 py-0.5 text-xs font-mono rounded border bg-blue-500/10 text-blue-400 border-blue-500/30">
                SANDBOX
              </span>
            </div>
            <p className="text-xs text-gray-400">
              AI-quoted repair fee • 100% verification-gated escrow capture
            </p>
          </div>
        </div>

        {quote && (
          <div className="text-right">
            <span className="text-2xl font-mono font-bold text-emerald-400">
              ${quote.bounty_amount.toFixed(2)}
            </span>
            <span className="text-xs text-gray-400 ml-1 font-mono">{quote.currency}</span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="py-6 text-center text-xs text-gray-400 animate-pulse">
          Calculating dynamic AI bounty quote via 13-feature XGBoost risk engine...
        </div>
      ) : quote ? (
        <div className="mt-4 space-y-4">
          {/* Risk Tier & Complexity */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="p-3 rounded-lg bg-[#111622] border border-gray-800">
              <div className="text-gray-400 mb-1">Predicted Complexity</div>
              <div className="flex items-center space-x-2">
                <span className={`px-2 py-0.5 rounded text-xs font-mono border ${getTierBadge(quote.risk_tier)}`}>
                  {quote.risk_tier} RISK
                </span>
                <span className="text-gray-300 font-mono">Score: {quote.complexity_score}/10</span>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-[#111622] border border-gray-800">
              <div className="text-gray-400 mb-1">Escrow Protocol</div>
              <div className="flex items-center space-x-1.5 text-cyan-400 font-mono">
                <ShieldCheck className="w-4 h-4 text-cyan-400" />
                <span>Verification Gated</span>
              </div>
            </div>
          </div>

          {/* Breakdown Toggle */}
          <div>
            <button
              type="button"
              onClick={() => setShowBreakdown(!showBreakdown)}
              className="flex items-center justify-between w-full px-3 py-2 text-xs rounded bg-[#131926] text-gray-300 hover:text-white transition-colors"
            >
              <span className="font-mono flex items-center space-x-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>Transparent AI Pricing Breakdown</span>
              </span>
              {showBreakdown ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>

            {showBreakdown && quote.breakdown && (
              <div className="mt-2 p-3 rounded bg-[#090d14] border border-gray-800 text-xs font-mono space-y-1.5 text-gray-300">
                <div className="flex justify-between">
                  <span className="text-gray-400">Base Agent Orchestration:</span>
                  <span>${quote.breakdown.base_fee?.toFixed(2) || '15.00'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">AST Complexity Delta:</span>
                  <span>${quote.breakdown.complexity_fee?.toFixed(2) || '5.00'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Blast Radius Churn:</span>
                  <span>${quote.breakdown.blast_radius_fee?.toFixed(2) || '4.00'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Docker Sandbox Compute:</span>
                  <span>${quote.breakdown.sandbox_compute_fee?.toFixed(2) || '5.00'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Nemotron 3.5 Token Budget:</span>
                  <span>${quote.breakdown.nemotron_reasoning_fee?.toFixed(2) || '4.00'}</span>
                </div>
                {quote.breakdown.severity_surcharge > 0 && (
                  <div className="flex justify-between text-rose-400">
                    <span>Critical Triggers ({quote.breakdown.detected_critical_factors?.join(', ')}):</span>
                    <span>+${quote.breakdown.severity_surcharge.toFixed(2)}</span>
                  </div>
                )}
                <div className="pt-2 border-t border-gray-800 flex justify-between font-bold text-white">
                  <span>Total Escrow:</span>
                  <span className="text-emerald-400">${quote.bounty_amount.toFixed(2)} USD</span>
                </div>
              </div>
            )}
          </div>

          {/* Escrow Guarantee Notice */}
          <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-xs text-gray-300 flex items-start space-x-2">
            <Lock className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <p>
              <strong className="text-emerald-400">Zero-Risk Guarantee:</strong> Bounty authorization is held in PayPal Sandbox escrow. Capture is only executed when Agent 04 certifies 100% passing tests in the isolated container.
            </p>
          </div>

          {/* Action / Funded State */}
          {activeOrder ? (
            <div className="p-3 rounded-lg bg-cyan-950/30 border border-cyan-500/40 text-xs flex items-center justify-between">
              <div className="flex items-center space-x-2 text-cyan-300">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>
                  Bounty Authorized: <strong>{activeOrder.order_id}</strong> (${activeOrder.amount} {activeOrder.currency})
                </span>
              </div>
              <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 font-mono text-[10px]">
                ESCROW HELD
              </span>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleFundWithPayPal}
              disabled={processingPayment}
              className="w-full flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg bg-[#0070BA] hover:bg-[#005ea6] text-white font-medium text-xs transition-all shadow-md shadow-blue-900/30 disabled:opacity-50"
            >
              <span className="font-bold tracking-wider">PayPal</span>
              <span>Checkout Sandbox (${quote.bounty_amount.toFixed(2)})</span>
            </button>
          )}

          {error && (
            <p className="text-xs text-rose-400 mt-1">{error}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

