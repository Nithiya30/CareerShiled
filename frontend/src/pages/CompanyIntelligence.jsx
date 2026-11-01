import React, { useState, useEffect, useCallback } from 'react';
import { 
  Building2, 
  Search, 
  MessageSquare, 
  Sparkles,
  FileCheck
} from 'lucide-react';
import CompanyReputation from '../components/CompanyReputation';
import ReviewCredibility from '../components/ReviewCredibility';
import ClaimCard from '../components/ClaimCard';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import api from '../services/api';

const QUICK_COMPANIES = [
  'Google',
  'Microsoft',
  'Amazon',
  'Apex Logistics',
  'Sunrise Artisanal Breads',
  'Meta'
];

const SAMPLE_CLAIMS = [
  "Company has poor work-life balance.",
  "Management provides strong career growth and mentorship.",
  "Salary and compensation are below market average.",
  "Job security is low with frequent restructuring.",
  "Great inclusive workplace culture."
];

export default function CompanyIntelligence({ initialCompany }) {
  const [companyName, setCompanyName] = useState(initialCompany || 'Google');
  const [investigationDomain, setInvestigationDomain] = useState('');
  const [investigationContact, setInvestigationContact] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [reputationData, setReputationData] = useState(null);
  const [investigationLoading, setInvestigationLoading] = useState(false);
  const [investigationError, setInvestigationError] = useState('');
  const [investigation, setInvestigation] = useState(null);
  const [investigationGraph, setInvestigationGraph] = useState(null);
  const [savedInvestigations, setSavedInvestigations] = useState([]);

  // Claim Analysis State
  const [claimText, setClaimText] = useState('Company has poor work-life balance.');
  const [claimLoading, setClaimLoading] = useState(false);
  const [claimResult, setClaimResult] = useState(null);
  const [claimError, setClaimError] = useState(null);

  const fetchReputation = useCallback(async (targetCompany) => {
    const comp = targetCompany || '';
    if (!comp.trim()) return;

    setLoading(true);
    setError(null);
    setClaimResult(null);

    try {
      const data = await api.analyzeCompanyReputation(comp.trim());
      setReputationData(data);
    } catch (err) {
      setError(err.message || 'Failed to retrieve company intelligence.');
      setReputationData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initialCompany) {
      setCompanyName(initialCompany);
      fetchReputation(initialCompany);
    } else {
      fetchReputation('Google');
    }
  }, [initialCompany, fetchReputation]);

  const refreshInvestigations = async () => {
    try {
      setSavedInvestigations(await api.getCompanyInvestigations());
    } catch (err) {
      setInvestigationError(err.message || 'Unable to load saved investigations.');
    }
  };

  useEffect(() => {
    let active = true;
    api.getCompanyInvestigations()
      .then((items) => {
        if (active) setSavedInvestigations(items);
      })
      .catch((err) => {
        if (active) {
          setInvestigationError(err.message || 'Unable to load saved investigations.');
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const handleInvestigation = async () => {
    if (!companyName.trim()) return;
    setInvestigationLoading(true);
    setInvestigationError('');
    try {
      const payload = { company_name: companyName.trim() };
      if (investigationDomain.trim()) payload.domain = investigationDomain.trim();
      if (investigationContact.trim()) payload.recruiter_email = investigationContact.trim();
      const saved = await api.createCompanyInvestigation(payload);
      setInvestigation(saved);
      setInvestigationGraph(await api.getCompanyInvestigationGraph(saved.id));
      await refreshInvestigations();
    } catch (err) {
      setInvestigationError(err.message || 'Unable to investigate this company.');
    } finally {
      setInvestigationLoading(false);
    }
  };

  const openInvestigation = async (id) => {
    setInvestigationError('');
    try {
      const [saved, graph] = await Promise.all([
        api.getCompanyInvestigation(id),
        api.getCompanyInvestigationGraph(id)
      ]);
      setInvestigation(saved);
      setInvestigationGraph(graph);
    } catch (err) {
      setInvestigationError(err.message || 'Unable to load this investigation.');
    }
  };

  const removeInvestigation = async (id) => {
    if (!window.confirm('Delete this saved company investigation and its evidence?')) return;
    setInvestigationError('');
    try {
      await api.deleteCompanyInvestigation(id);
      if (investigation?.id === id) {
        setInvestigation(null);
        setInvestigationGraph(null);
      }
      await refreshInvestigations();
    } catch (err) {
      setInvestigationError(err.message || 'Unable to delete this investigation.');
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchReputation(companyName);
  };

  const handleClaimSubmit = async (e) => {
    e.preventDefault();
    if (!claimText.trim() || !companyName.trim()) return;

    setClaimLoading(true);
    setClaimError(null);

    try {
      const result = await api.analyzeClaim(companyName.trim(), claimText.trim());
      setClaimResult(result);
    } catch (err) {
      setClaimError(err.message || 'Failed to analyze claim evidence.');
    } finally {
      setClaimLoading(false);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Banner & Search */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/30">
            Area 2: Company Intelligence
          </span>
          <span className="text-xs text-slate-400">• Independent Workplace Reputation</span>
        </div>
        <h2 className="text-xl font-bold text-slate-100">Company Intelligence & Claims</h2>
        <p className="text-xs text-slate-300 mt-1">
          Evaluate authentic employee experiences, aspect-based sentiment, and verify public claims.
          Remember: Company reputation is strictly separated from recruitment fraud risk.
        </p>

        {/* Search bar */}
        <form onSubmit={handleSearch} className="mt-5 flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Building2 className="w-4 h-4 text-cyan-400 absolute left-3 top-3" />
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Enter company name (e.g. Google, Microsoft, Amazon)..."
              required
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>
          <button
            type="submit"
            className="px-5 py-2 rounded text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all inline-flex items-center justify-center gap-2 shrink-0"
          >
            <Search className="w-4 h-4" />
            <span>Analyze Company</span>
          </button>
          <button
            type="button"
            onClick={handleInvestigation}
            disabled={investigationLoading || !companyName.trim()}
            className="px-5 py-2 rounded text-xs font-semibold bg-shield-surface hover:border-cyan-500 border border-shield-border text-cyan-300 transition-all inline-flex items-center justify-center gap-2 shrink-0 disabled:opacity-60"
          >
            <FileCheck className="w-4 h-4" />
            <span>{investigationLoading ? 'Investigating...' : 'Investigate & Save'}</span>
          </button>
        </form>
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="investigation-domain" className="mb-1 block text-[11px] text-slate-400">Optional website or domain for saved investigation</label>
            <input
              id="investigation-domain"
              type="text"
              value={investigationDomain}
              onChange={(event) => setInvestigationDomain(event.target.value)}
              placeholder="example.com or https://example.com"
              maxLength={255}
              className="w-full rounded border border-shield-border bg-shield-surface px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-500"
            />
          </div>
          <div>
            <label htmlFor="investigation-contact" className="mb-1 block text-[11px] text-slate-400">Optional recruiter/contact email (only if needed)</label>
            <input
              id="investigation-contact"
              type="email"
              value={investigationContact}
              onChange={(event) => setInvestigationContact(event.target.value)}
              placeholder="contact@example.com"
              maxLength={320}
              className="w-full rounded border border-shield-border bg-shield-surface px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none focus:border-cyan-500"
            />
          </div>
        </div>

        {/* Quick select presets */}
        <div className="flex items-center gap-2 mt-3 text-xs text-slate-400">
          <span className="text-[11px] font-mono">Quick Search:</span>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_COMPANIES.map((comp) => (
              <button
                key={comp}
                type="button"
                onClick={() => {
                  setCompanyName(comp);
                  fetchReputation(comp);
                }}
                className="px-2 py-0.5 rounded bg-shield-surface border border-shield-border hover:border-cyan-500/40 hover:text-cyan-300 text-[11px] text-slate-300"
              >
                {comp}
              </button>
            ))}
          </div>
        </div>
      </div>

      <section className="bg-shield-card border border-shield-border rounded-lg p-5 space-y-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100">Private investigations</h3>
          <p className="text-xs text-slate-400 mt-1">
            Saved reports are visible only to the account that created them. Candidate domains and heuristic signals are not proof of company identity.
          </p>
        </div>
        {investigationError && (
          <p role="alert" className="rounded border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300">
            {investigationError}
          </p>
        )}
        {savedInvestigations.length > 0 ? (
          <ul className="space-y-2">
            {savedInvestigations.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 rounded border border-shield-border bg-shield-surface p-3">
                <div className="min-w-0">
                  <p className="truncate text-sm text-slate-200">{item.company_name}</p>
                  <p className="text-[11px] text-slate-500">
                    {item.domain || 'No domain supplied'} · {item.created_at ? new Date(item.created_at).toLocaleString() : 'Date unavailable'}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <button type="button" onClick={() => openInvestigation(item.id)} className="text-xs text-cyan-300 hover:text-cyan-200">Open</button>
                  <button type="button" onClick={() => removeInvestigation(item.id)} className="text-xs text-rose-300 hover:text-rose-200">Delete</button>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="rounded border border-dashed border-shield-border p-4 text-xs text-slate-400">
            No saved investigations yet.
          </p>
        )}

        {investigation && (
          <div className="space-y-4 border-t border-shield-border pt-4">
            <div>
              <h4 className="font-semibold text-slate-100">{investigation.company_name} · Investigation report</h4>
              <p className="text-[11px] text-slate-500">
                Created {investigation.created_at ? new Date(investigation.created_at).toLocaleString() : 'at an unknown time'} · {investigation.domain || 'No domain supplied'}
              </p>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(investigation.assessments || {}).map(([key, value]) => (
                <article key={key} className="rounded border border-shield-border bg-shield-surface p-3">
                  <h5 className="text-xs font-semibold text-cyan-300">{key.replaceAll('_', ' ')}</h5>
                  <p className="mt-1 text-xs text-slate-200">{value.label || value.status || 'Unknown'}</p>
                  <p className="mt-1 text-xs text-slate-400">{value.summary || value.limitations?.join(' ') || 'No further details available.'}</p>
                  {value.review_count !== undefined && (
                    <p className="mt-2 text-[11px] text-slate-500">
                      {value.review_count} local review records · {value.date_range?.start || 'start unavailable'} to {value.date_range?.end || 'end unavailable'}
                    </p>
                  )}
                </article>
              ))}
            </div>
            <div>
              <h5 className="mb-2 text-xs font-semibold text-slate-200">Evidence and limitations</h5>
              <ul className="space-y-2">
                {(investigation.evidence || []).map((item) => (
                  <li key={item.id} className="rounded border border-shield-border bg-shield-surface p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-medium text-slate-200">{item.source_name}</span>
                      <span className="rounded border border-cyan-500/30 px-2 py-0.5 text-[10px] uppercase text-cyan-300">{item.status}</span>
                    </div>
                    <p className="mt-1 text-xs text-slate-300">{item.finding}</p>
                    <p className="mt-1 text-xs text-slate-400">{item.factual_summary}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{item.explanation} {item.limitations}</p>
                    <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">
                      <span>Reliability: {item.source_reliability}</span>
                      <span>Retrieved: {item.retrieved_at ? new Date(item.retrieved_at).toLocaleString() : 'unavailable'}</span>
                      {item.source_url && (
                        <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="text-cyan-300 hover:text-cyan-200">
                          Open source
                        </a>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            {investigation.information_types && (
              <div className="rounded border border-shield-border bg-shield-surface p-3">
                <h5 className="text-xs font-semibold text-slate-200">Information categories</h5>
                <p className="mt-1 text-[11px] text-slate-400">
                  Verified facts: {(investigation.information_types.verified_facts || []).length} ·
                  Source-reported: {(investigation.information_types.source_reported || []).length} ·
                  Model interpretations: {(investigation.information_types.model_interpretations || []).length} ·
                  Conflicting: {(investigation.information_types.conflicting_evidence || []).length} ·
                  Unavailable: {(investigation.information_types.unknown_or_unavailable || []).length}
                </p>
                {(investigation.limitations || []).map((item, index) => (
                  <p key={index} className="mt-1 text-[11px] text-slate-500">{item}</p>
                ))}
              </div>
            )}
            <div>
              <h5 className="mb-2 text-xs font-semibold text-slate-200">Relationship graph</h5>
              <p className="mb-2 text-[11px] text-slate-500">
                Relationships are investigation-scoped claims or source links. They are not proof of corporate ownership or employment.
              </p>
              {investigationGraph?.relationships?.length ? (
                <ul className="space-y-2">
                  {investigationGraph.relationships.map((edge) => {
                    const entities = new Map(
                      (investigationGraph.entities || []).map((entity) => [entity.id, entity])
                    );
                    const source = entities.get(edge.source_entity_id);
                    const target = entities.get(edge.target_entity_id);
                    return (
                      <li key={edge.id} className="rounded border border-shield-border bg-shield-surface p-3">
                        <p className="text-xs font-medium text-slate-200">
                          {source?.display_name || 'Unknown'} → {edge.relationship_type.replaceAll('_', ' ')} → {target?.display_name || 'Unknown'}
                        </p>
                        <p className="mt-1 text-[11px] text-cyan-300">{edge.status}</p>
                        <p className="mt-1 text-xs text-slate-400">{edge.explanation} {edge.limitations}</p>
                        {edge.evidence?.length > 0 && (
                          <ul className="mt-2 space-y-1 border-t border-shield-border pt-2">
                            {edge.evidence.map((item) => (
                              <li key={item.id} className="text-[11px] text-slate-500">
                                {item.source_name}: {item.factual_summary}
                                {item.source_url && (
                                  <> · <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="text-cyan-300 hover:text-cyan-200">source</a></>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="rounded border border-dashed border-shield-border p-3 text-xs text-slate-500">
                  No relationships were recorded for this investigation.
                </p>
              )}
            </div>
          </div>
        )}
      </section>

      <ReviewCredibility companyName={companyName} setCompanyName={setCompanyName} />

      {loading && <LoadingState message={`Gathering intelligence for ${companyName}...`} />}

      {error && (
        <ErrorState
          title="Company Intelligence Error"
          message={error}
          onRetry={() => fetchReputation(companyName)}
        />
      )}

      {/* Main Intelligence Results */}
      {!loading && reputationData && (
        <div className="space-y-6">
          {/* Company Profile Card (Section 14) */}
          <div className="bg-shield-card border border-shield-border rounded-lg p-5">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-shield-border/60">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-lg bg-shield-surface border border-shield-border flex items-center justify-center text-cyan-400">
                  <Building2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-100">{reputationData.company_name}</h3>
                  <p className="text-xs text-slate-400">
                    {reputationData.industry || 'Industry not provided'} • {reputationData.location || 'Location not provided'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-2.5 py-1 rounded bg-shield-surface border border-shield-border text-slate-300">
                  Indexed review records: {reputationData.total_reviews ?? 0}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 text-xs font-mono">
              <div className="bg-shield-surface border border-shield-border p-2.5 rounded">
                <span className="text-slate-400 block text-[10px]">OFFICIAL WEBSITE</span>
                <span className="text-slate-200 truncate block mt-0.5">{reputationData.website || 'Not provided'}</span>
              </div>
              <div className="bg-shield-surface border border-shield-border p-2.5 rounded">
                <span className="text-slate-400 block text-[10px]">DOMAIN STATUS</span>
                <span className="text-slate-200 font-semibold block mt-0.5">{reputationData.domain_status || 'Not provided'}</span>
              </div>
              <div className="bg-shield-surface border border-shield-border p-2.5 rounded">
                <span className="text-slate-400 block text-[10px]">CAREER PAGE</span>
                <span className="text-slate-200 block mt-0.5">{reputationData.career_page || 'Not provided'}</span>
              </div>
              <div className="bg-shield-surface border border-shield-border p-2.5 rounded">
                <span className="text-slate-400 block text-[10px]">REPUTATION CONFIDENCE</span>
                <span className="text-cyan-400 font-semibold block mt-0.5">
                  {typeof reputationData.confidence === 'number' ? `${Math.round((reputationData.confidence <= 1 ? reputationData.confidence * 100 : reputationData.confidence))}%` : 'Not available'}
                </span>
              </div>
            </div>
          </div>

          {/* Company Reputation & Reviews (Sections 15 & 16) */}
          <CompanyReputation reputationData={reputationData} />

          {/* Public Claim Analysis (Sections 17 & 18) */}
          <div className="bg-shield-card border border-shield-border rounded-lg p-6 space-y-4">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <FileCheck className="w-4 h-4 text-cyan-400" />
                <h3 className="text-base font-semibold text-slate-100">Public Claim Analysis</h3>
              </div>
              <p className="text-xs text-slate-400">
                Evaluate public statements or rumors against normalized employee feedback.
                Claims are classified using multi-factor corroboration, not single reviews.
              </p>
            </div>

            {/* Claim input form */}
            <form onSubmit={handleClaimSubmit} className="space-y-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <MessageSquare className="w-4 h-4 text-cyan-400 absolute left-3 top-3" />
                  <input
                    type="text"
                    value={claimText}
                    onChange={(e) => setClaimText(e.target.value)}
                    placeholder="Enter claim to verify (e.g. 'Company has poor work-life balance.')..."
                    required
                    className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded pl-9 pr-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={claimLoading}
                  className="px-4 py-2 rounded text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all shrink-0 inline-flex items-center gap-1.5"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{claimLoading ? 'Verifying...' : 'Verify Claim'}</span>
                </button>
              </div>

              {/* Sample claim chips */}
              <div className="flex items-center gap-1.5 text-xs text-slate-400">
                <span className="text-[11px] font-mono">Sample Claims:</span>
                <div className="flex flex-wrap gap-1">
                  {SAMPLE_CLAIMS.map((claim, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setClaimText(claim)}
                      className="px-2 py-0.5 rounded bg-shield-surface border border-shield-border hover:border-cyan-500/40 text-[10px] text-slate-300"
                    >
                      {claim}
                    </button>
                  ))}
                </div>
              </div>
            </form>

            {claimError && (
              <div className="bg-rose-950/20 border border-rose-500/30 rounded p-3 text-xs text-rose-300">
                {claimError}
              </div>
            )}

            {claimLoading && (
              <div className="py-6">
                <LoadingState message="Cross-corroborating claim against employee review corpora..." />
              </div>
            )}

            {claimResult && !claimLoading && (
              <div className="mt-4">
                <ClaimCard claimData={claimResult} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
