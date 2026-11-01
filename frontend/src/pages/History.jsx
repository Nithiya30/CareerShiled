import React, { useState, useEffect } from 'react';
import {
  Search,
  ExternalLink,
  Building2,
  Briefcase,
  RefreshCw,
  HelpCircle
} from 'lucide-react';
import RiskBadge from '../components/RiskBadge';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import api from '../services/api';

export default function History({ onViewAnalysis }) {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterRisk, setFilterRisk] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearchQuery, setDebouncedSearchQuery] = useState('');

  // Debounce search query changes to prevent excessive API requests
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchQuery(searchQuery.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch history from server whenever risk filter or debounced search changes
  useEffect(() => {
    let isCancelled = false;

    const loadHistory = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = {};
        if (filterRisk && filterRisk !== 'ALL') {
          params.risk = filterRisk;
        }
        if (debouncedSearchQuery && debouncedSearchQuery.trim()) {
          params.search = debouncedSearchQuery.trim();
        }
        const data = await api.getHistory(params);
        if (!isCancelled) {
          setAnalyses(data?.analyses || []);
        }
      } catch (err) {
        if (!isCancelled) {
          setError(err.message || 'Failed to fetch analysis history.');
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [filterRisk, debouncedSearchQuery]);

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (filterRisk && filterRisk !== 'ALL') {
        params.risk = filterRisk;
      }
      if (debouncedSearchQuery && debouncedSearchQuery.trim()) {
        params.search = debouncedSearchQuery.trim();
      }
      const data = await api.getHistory(params);
      setAnalyses(data?.analyses || []);
    } catch (err) {
      setError(err.message || 'Failed to fetch analysis history.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-slate-100">Analysis History</h2>
            <p className="text-xs text-slate-300 mt-1">
              Audit record of past recruitment investigations with multi-evidence scores
            </p>
          </div>
          <button
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-slate-300 border border-shield-border bg-shield-surface hover:text-white transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>

        {/* Filters and Search Bar */}
        <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-3">
          {/* Search box */}
          <div className="relative md:col-span-2">
            <Search className="w-4 h-4 text-cyan-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by company or job title..."
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Risk Level Filter */}
          <div className="flex items-center gap-1.5 bg-shield-surface border border-shield-border rounded p-1">
            <button
              onClick={() => setFilterRisk('ALL')}
              className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${filterRisk === 'ALL' ? 'bg-shield-card text-cyan-400 shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              All
            </button>
            <button
              onClick={() => setFilterRisk('LEGITIMATE')}
              className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${filterRisk === 'LEGITIMATE' ? 'bg-shield-card text-emerald-400 shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Legitimate
            </button>
            <button
              onClick={() => setFilterRisk('UNCERTAIN')}
              className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${filterRisk === 'UNCERTAIN' ? 'bg-shield-card text-amber-400 shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Needs Verification
            </button>
            <button
              onClick={() => setFilterRisk('FRAUDULENT')}
              className={`flex-1 py-1 text-[11px] font-medium rounded transition-colors ${filterRisk === 'FRAUDULENT' ? 'bg-shield-card text-rose-400 shadow' : 'text-slate-400 hover:text-slate-200'}`}
            >
              Fraudulent
            </button>
          </div>
        </div>
      </div>

      {loading && <LoadingState message="Loading historical records..." />}

      {error && (
        <ErrorState message={error} onRetry={handleRefresh} />
      )}

      {!loading && !error && (
        <div className="bg-shield-card border border-shield-border rounded-lg overflow-hidden">
          {analyses.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-shield-surface/60 border-b border-shield-border text-slate-400 uppercase font-mono text-[11px]">
                    <th className="py-3 px-4 font-medium">Company</th>
                    <th className="py-3 px-4 font-medium">Job Title</th>
                    <th className="py-3 px-4 font-medium">Trust Score</th>
                    <th className="py-3 px-4 font-medium">Risk Level</th>
                    <th className="py-3 px-4 font-medium">Date & Time</th>
                    <th className="py-3 px-4 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-shield-border/60">
                  {analyses.map((item) => (
                    <tr key={item.id} className="hover:bg-shield-surface/50 transition-colors">
                      <td className="py-3.5 px-4 font-medium text-slate-200">
                        <div className="flex items-center gap-2">
                          <Building2 className="w-3.5 h-3.5 text-slate-400" />
                          <span>{item.company_name || 'Unspecified'}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 text-slate-300">
                        <div className="flex items-center gap-2">
                          <Briefcase className="w-3.5 h-3.5 text-cyan-400/80" />
                          <span>{item.job_title}</span>
                        </div>
                        <details className="mt-2 max-w-xl">
                          <summary className="cursor-pointer text-[11px] text-cyan-400 hover:text-cyan-300">
                            View submitted details
                          </summary>
                          <div className="mt-2 space-y-1 rounded border border-shield-border bg-shield-surface p-3 text-[11px] text-slate-300">
                            <p><span className="text-slate-400">Recruiter email:</span> {item.recruiter_email || 'Not provided'}</p>
                            <p><span className="text-slate-400">Company website:</span> {item.company_website || 'Not provided'}</p>
                            <p><span className="text-slate-400">Location:</span> {item.location || 'Not provided'}</p>
                            <p><span className="text-slate-400">Employment type:</span> {item.employment_type || 'Not provided'}</p>
                            <p><span className="text-slate-400">Salary:</span> {item.salary || 'Not provided'}</p>
                            <p><span className="text-slate-400">Job description:</span> {item.job_description || 'Not provided'}</p>
                            <p><span className="text-slate-400">Requirements:</span> {item.requirements || 'Not provided'}</p>
                            <p><span className="text-slate-400">Benefits:</span> {item.benefits || 'Not provided'}</p>
                          </div>
                        </details>
                      </td>
                      <td className="py-3.5 px-4 font-mono font-bold text-slate-100">
                        {Math.round(item.trust_score)} / 100
                      </td>
                      <td className="py-3.5 px-4">
                        <RiskBadge riskLevel={item.risk_level} />
                      </td>
                      <td className="py-3.5 px-4 font-mono text-slate-400">
                        {item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => onViewAnalysis(item.id)}
                          className="px-3 py-1.5 rounded border border-shield-border text-cyan-400 hover:bg-shield-surface text-xs font-mono inline-flex items-center gap-1.5 transition-colors"
                        >
                          <span>View Report</span>
                          <ExternalLink className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-center py-16 px-4">
              <HelpCircle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm text-slate-300 font-medium">No matching analyses found</p>
              <p className="text-xs text-slate-400 mt-1">
                {searchQuery || filterRisk !== 'ALL'
                  ? 'Try adjusting your search criteria or risk filter.'
                  : 'Start by analyzing a recruitment offer to log results here.'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
