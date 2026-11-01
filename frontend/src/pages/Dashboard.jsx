import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  ExternalLink,
  FileText,
  HelpCircle,
  RefreshCw,
  ShieldAlert,
  ShieldCheck
} from 'lucide-react';
import StatCard from '../components/StatCard';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import api from '../services/api';

export default function Dashboard({ onNavigate, onViewAnalysis }) {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const history = await api.getHistory();
      setAnalyses(history.analyses || []);
    } catch (err) {
      setError(err.message || 'Failed to load your analyses.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return <LoadingState message="Loading your analyses..." />;
  }

  if (error) {
    return <ErrorState message={error} onRetry={fetchData} />;
  }

  const total = analyses.length;
  const legitimateCount = analyses.filter((item) => item.risk_level === 'Likely Legitimate').length;
  const verificationCount = analyses.filter((item) => item.risk_level === 'Needs Verification').length;
  const fraudulentCount = analyses.filter((item) => item.risk_level === 'Likely Fraudulent').length;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-slate-100">Your Dashboard</h2>
          <p className="text-sm text-slate-400 mt-1">Job analyses submitted from your account.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={fetchData}
            className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-sm text-slate-300 border border-shield-border bg-shield-card hover:text-white"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
          <button
            onClick={() => onNavigate('analyze')}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold bg-cyan-600 hover:bg-cyan-500 text-white"
          >
            Analyze a job
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard title="Your Analyses" value={total} subtitle="Submitted job postings" icon={FileText} color="blue" />
        <StatCard title="Likely Legitimate" value={legitimateCount} subtitle="From your saved analyses" icon={ShieldCheck} color="emerald" />
        <StatCard title="Needs Verification" value={verificationCount} subtitle="From your saved analyses" icon={AlertTriangle} color="amber" />
        <StatCard title="Likely Fraudulent" value={fraudulentCount} subtitle="From your saved analyses" icon={ShieldAlert} color="rose" />
      </div>

      <section className="bg-shield-card border border-shield-border rounded-lg p-5">
        <div className="flex items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-100">Your Recent Analyses</h3>
            <p className="text-sm text-slate-400 mt-1">Saved results for the job postings you submitted.</p>
          </div>
          {total > 0 && (
            <button
              onClick={() => onNavigate('history')}
              className="text-sm text-cyan-400 hover:text-cyan-300 inline-flex items-center gap-1"
            >
              All history
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>

        {total === 0 ? (
          <div className="text-center py-12 text-slate-400 border border-dashed border-shield-border rounded">
            <HelpCircle className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            <p className="text-sm">You have no saved analyses yet.</p>
            <button
              onClick={() => onNavigate('analyze')}
              className="mt-3 text-sm text-cyan-400 hover:text-cyan-300"
            >
              Analyze your first job
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-shield-border text-xs text-slate-400 uppercase">
                  <th className="pb-3 pr-4 font-medium">Company</th>
                  <th className="pb-3 pr-4 font-medium">Job Title</th>
                  <th className="pb-3 pr-4 font-medium">Trust Score</th>
                  <th className="pb-3 pr-4 font-medium">Risk Level</th>
                  <th className="pb-3 pr-4 font-medium">Date</th>
                  <th className="pb-3 font-medium text-right">Report</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-shield-border/60">
                {analyses.slice(0, 5).map((item) => (
                  <tr key={item.id} className="hover:bg-shield-surface/50">
                    <td className="py-3 pr-4 text-slate-200">{item.company_name || 'Not provided'}</td>
                    <td className="py-3 pr-4 text-slate-300">{item.job_title}</td>
                    <td className="py-3 pr-4 font-mono font-bold text-slate-100">
                      {Math.round(item.trust_score)} / 100
                    </td>
                    <td className="py-3 pr-4"><RiskBadge riskLevel={item.risk_level} /></td>
                    <td className="py-3 pr-4 text-slate-400">
                      {item.created_at ? new Date(item.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="py-3 text-right">
                      <button
                        onClick={() => onViewAnalysis(item.id)}
                        className="inline-flex items-center gap-1 text-cyan-400 hover:text-cyan-300"
                      >
                        View
                        <ExternalLink className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
