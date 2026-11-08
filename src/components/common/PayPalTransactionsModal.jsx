import React, { useState, useEffect } from 'react';
import { X, DollarSign, CheckCircle2, Clock, ShieldAlert, ArrowUpRight, RefreshCw } from 'lucide-react';
import api from '../../services/api';

export default function PayPalTransactionsModal({ isOpen, onClose }) {
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTransactions = async () => {
    try {
      setLoading(true);
      const data = await api.getPayPalTransactions(50);
      setTransactions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to load PayPal transactions:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchTransactions();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const totalFunded = transactions.reduce((acc, t) => acc + (t.amount || 0), 0);
  const totalCaptured = transactions
    .filter(t => t.status === 'COMPLETED')
    .reduce((acc, t) => acc + (t.amount || 0), 0);
  const activeEscrow = totalFunded - totalCaptured;

  const getStatusBadge = (status) => {
    switch (status) {
      case 'COMPLETED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 mr-1" /> CAPTURED
          </span>
        );
      case 'CREATED':
      case 'APPROVED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <Clock className="w-3 h-3 mr-1" /> IN ESCROW
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-gray-500/10 text-gray-400 border border-gray-500/30">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-4xl rounded-xl border border-gray-800 bg-[#0c1017] p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-gray-800">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/30">
              <DollarSign className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-lg font-bold text-white">PayPal Bug Bounty Ledger</h2>
                <span className="px-2 py-0.5 text-xs font-mono rounded bg-blue-500/10 text-blue-400 border border-blue-500/30">
                  DEVELOPER SANDBOX
                </span>
              </div>
              <p className="text-xs text-gray-400">
                Transparent escrow & payout record for autonomous bug investigations
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-3 gap-4 my-5">
          <div className="p-3.5 rounded-lg bg-[#111622] border border-gray-800">
            <div className="text-xs text-gray-400 mb-1">Total Bounties Quoted</div>
            <div className="text-xl font-mono font-bold text-white">
              ${totalFunded.toFixed(2)} <span className="text-xs text-gray-500">USD</span>
            </div>
          </div>
          <div className="p-3.5 rounded-lg bg-[#111622] border border-emerald-500/30">
            <div className="text-xs text-emerald-400 mb-1">Captured (Verified Fixes)</div>
            <div className="text-xl font-mono font-bold text-emerald-400">
              ${totalCaptured.toFixed(2)} <span className="text-xs text-gray-500">USD</span>
            </div>
          </div>
          <div className="p-3.5 rounded-lg bg-[#111622] border border-cyan-500/30">
            <div className="text-xs text-cyan-400 mb-1">Active in Escrow</div>
            <div className="text-xl font-mono font-bold text-cyan-400">
              ${activeEscrow.toFixed(2)} <span className="text-xs text-gray-500">USD</span>
            </div>
          </div>
        </div>

        {/* Ledger Table */}
        <div className="overflow-hidden rounded-lg border border-gray-800 bg-[#090d14]">
          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="p-8 text-center text-xs text-gray-400 animate-pulse">
                Loading PayPal transactions from SQLite ledger...
              </div>
            ) : transactions.length === 0 ? (
              <div className="p-8 text-center text-xs text-gray-400">
                No PayPal bounty transactions recorded yet. Fund a bug rescue to see real-time escrow records!
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="bg-[#111622] text-gray-400 font-mono border-b border-gray-800">
                  <tr>
                    <th className="py-2.5 px-4">Order ID</th>
                    <th className="py-2.5 px-4">Target Repo & Issue</th>
                    <th className="py-2.5 px-4">Bounty Amount</th>
                    <th className="py-2.5 px-4">Escrow Status</th>
                    <th className="py-2.5 px-4">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 font-mono text-gray-300">
                  {transactions.map((tx) => (
                    <tr key={tx.order_id} className="hover:bg-gray-800/30 transition-colors">
                      <td className="py-2.5 px-4 text-cyan-400 font-bold">
                        {tx.order_id}
                      </td>
                      <td className="py-2.5 px-4 text-gray-300">
                        {tx.repository || 'Custom Repo'} {tx.issue_number ? `#${tx.issue_number}` : ''}
                      </td>
                      <td className="py-2.5 px-4 text-emerald-400 font-bold">
                        ${Number(tx.amount || 0).toFixed(2)} {tx.currency}
                      </td>
                      <td className="py-2.5 px-4">
                        {getStatusBadge(tx.status)}
                      </td>
                      <td className="py-2.5 px-4 text-gray-500 text-[11px]">
                        {tx.created_at ? new Date(tx.created_at * 1000).toLocaleString() : 'Just now'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="mt-4 flex items-center justify-between pt-3 border-t border-gray-800 text-xs text-gray-500">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>PayPal Sandbox Orders API v2 Connected</span>
          </div>
          <button
            onClick={fetchTransactions}
            className="flex items-center space-x-1 text-gray-400 hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Ledger</span>
          </button>
        </div>
      </div>
    </div>
  );
}

