import React, { useState } from 'react';
import { AlertTriangle, CheckCircle2, FileSearch, HelpCircle, ShieldCheck, Sparkles } from 'lucide-react';
import api from '../services/api';

const percentage = (value) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available';
  return `${Math.round((value <= 1 ? value * 100 : value))}%`;
};

const scorePercentage = (value) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available';
  return `${Math.round((value <= 1 ? value * 100 : value))}/100`;
};

const listify = (value) => {
  if (Array.isArray(value)) return value;
  return value ? [value] : [];
};

const statusStyle = (state) => {
  const normalized = String(state || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (['credible', 'verified', 'high_credibility'].includes(normalized)) {
    return { label: state, classes: 'bg-emerald-950/40 text-emerald-300 border-emerald-500/30', Icon: CheckCircle2 };
  }
  if (['suspicious', 'low_credibility', 'likely_fake'].includes(normalized)) {
    return { label: state, classes: 'bg-rose-950/40 text-rose-300 border-rose-500/30', Icon: AlertTriangle };
  }
  if (['needs_verification', 'uncertain', 'mixed'].includes(normalized)) {
    return { label: String(state).replace(/[_-]/g, ' '), classes: 'bg-amber-950/40 text-amber-300 border-amber-500/30', Icon: HelpCircle };
  }
  return { label: state || 'Not assessed', classes: 'bg-slate-800 text-slate-300 border-slate-700', Icon: HelpCircle };
};

function evidenceText(item) {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item ?? '');
  return item.evidence_text || item.text || item.description || item.title || JSON.stringify(item);
}

function ReviewResult({ result }) {
  const state = statusStyle(result.credibility_state);
  const StateIcon = state.Icon;
  const claims = listify(result.claims);
  const evidence = listify(result.supporting_evidence);
  const reasons = listify(result.reasons);
  const duplicate = result.duplicate_warning;
  const duplicateWarning = typeof duplicate === 'object' && duplicate !== null
    ? duplicate.message || duplicate.explanation || 'A similar or duplicate review was detected.'
    : typeof duplicate === 'string' && duplicate
      ? duplicate
      : duplicate
        ? 'A similar or duplicate review was detected.'
        : null;

  return (
    <section className="bg-shield-card border border-shield-border rounded-lg p-5 space-y-4" aria-labelledby="review-result-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] text-slate-400 uppercase tracking-wider">Review credibility assessment</p>
          <h4 id="review-result-heading" className="text-base font-semibold text-slate-100 mt-1">
            {result.company_name || 'Submitted review'}
          </h4>
          {result.review_id && <p className="text-[11px] text-slate-500 mt-1">Review ID: {result.review_id}</p>}
        </div>
        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded border text-xs font-medium capitalize ${state.classes}`}>
          <StateIcon className="w-3.5 h-3.5" aria-hidden="true" />
          {state.label}
        </span>
      </div>

      <blockquote className="border-l-2 border-cyan-500/60 pl-3 text-sm text-slate-300 whitespace-pre-wrap">
        {result.review_text}
      </blockquote>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-shield-surface border border-shield-border rounded p-3">
          <span className="block text-[10px] text-slate-400 uppercase">Credibility score</span>
          <span className="text-lg font-semibold text-cyan-300">{scorePercentage(result.credibility_score)}</span>
        </div>
        <div className="bg-shield-surface border border-shield-border rounded p-3">
          <span className="block text-[10px] text-slate-400 uppercase">Confidence</span>
          <span className="text-lg font-semibold text-slate-100">{percentage(result.confidence)}</span>
        </div>
        <div className="bg-shield-surface border border-shield-border rounded p-3">
          <span className="block text-[10px] text-slate-400 uppercase">Review quality</span>
          <span className="text-lg font-semibold text-slate-100">{scorePercentage(result.quality_score)}</span>
        </div>
        <div className="bg-shield-surface border border-shield-border rounded p-3">
          <span className="block text-[10px] text-slate-400 uppercase">Similarity</span>
          <span className="text-lg font-semibold text-slate-100">{percentage(result.similarity_score)}</span>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-300">
        <span><strong className="text-slate-400">Sentiment:</strong> {result.sentiment || 'Not available'}</span>
        <span><strong className="text-slate-400">Claims identified:</strong> {claims.length}</span>
      </div>

      {duplicateWarning && (
        <div role="status" className="flex items-start gap-2 rounded border border-amber-500/30 bg-amber-950/20 p-3 text-xs text-amber-200">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
          <span><strong>Possible duplicate:</strong> {duplicateWarning}</span>
        </div>
      )}

      {claims.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-200 mb-2">Claims in this review</h5>
          <ul className="space-y-2">
            {claims.map((claim, index) => (
              <li key={`${claim.claim_type || 'claim'}-${index}`} className="bg-shield-surface border border-shield-border rounded p-3">
                <div className="flex flex-wrap justify-between gap-2 text-xs">
                  <span className="font-medium text-slate-200">{claim.claim_text || 'Claim'}</span>
                  <span className="text-cyan-300 capitalize">{String(claim.verification_status || 'unverified').replace(/[_-]/g, ' ')}</span>
                </div>
                {claim.claim_type && <p className="text-[11px] text-slate-400 mt-1">Type: {String(claim.claim_type).replace(/[_-]/g, ' ')}</p>}
                {claim.explanation && <p className="text-xs text-slate-300 mt-1">{claim.explanation}</p>}
                {typeof claim.confidence === 'number' && <p className="text-[11px] text-slate-400 mt-1">Claim confidence: {percentage(claim.confidence)}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {evidence.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-200 mb-2">Supporting evidence</h5>
          <ul className="space-y-1.5">
            {evidence.map((item, index) => (
              <li key={index} className="text-xs text-slate-300 flex items-start gap-2">
                <ShieldCheck className="w-3.5 h-3.5 text-cyan-400 mt-0.5 shrink-0" aria-hidden="true" />
                <span>{evidenceText(item)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.explanation && (
        <div className="rounded border border-shield-border bg-shield-surface/60 p-3">
          <h5 className="text-xs font-semibold text-slate-200 mb-1">Assessment explanation</h5>
          <p className="text-xs text-slate-300 leading-relaxed">{result.explanation}</p>
        </div>
      )}

      {reasons.length > 0 && (
        <div>
          <h5 className="text-xs font-semibold text-slate-200 mb-1">Signals considered</h5>
          <ul className="list-disc list-inside space-y-1 text-xs text-slate-400">
            {reasons.map((reason, index) => <li key={index}>{evidenceText(reason)}</li>)}
          </ul>
        </div>
      )}
    </section>
  );
}

export default function ReviewCredibility({ companyName, setCompanyName }) {
  const [reviewText, setReviewText] = useState('');
  const [metadata, setMetadata] = useState({
    source_type: '',
    source_name: '',
    source_url: '',
    role: '',
    location: '',
    review_date: ''
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const updateMetadata = (field) => (event) => {
    setMetadata((current) => ({ ...current, [field]: event.target.value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!companyName.trim() || !reviewText.trim()) return;

    const payload = { company_name: companyName.trim(), review_text: reviewText.trim() };
    Object.entries(metadata).forEach(([key, value]) => {
      if (value.trim()) payload[key] = value.trim();
    });
    setLoading(true);
    setError('');
    try {
      setResult(await api.analyzeReview(payload));
    } catch (err) {
      setError(err.message || 'Unable to analyze this review. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="bg-shield-card border border-shield-border rounded-lg p-5 space-y-4" aria-labelledby="review-submit-heading">
      <div>
        <div className="flex items-center gap-2 mb-1">
          <FileSearch className="w-4 h-4 text-cyan-400" aria-hidden="true" />
          <h3 id="review-submit-heading" className="text-base font-semibold text-slate-100">Submit a workplace review</h3>
        </div>
        <p className="text-xs text-slate-400">
          Analyze a review for credibility, sentiment, specific claims, and possible duplication. This is an evidence-based signal, not a definitive judgment.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label htmlFor="review-company" className="block text-xs font-medium text-slate-300 mb-1">Company name <span aria-hidden="true">*</span></label>
          <input
            id="review-company"
            type="text"
            value={companyName}
            onChange={(event) => setCompanyName(event.target.value)}
            required
            className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none"
          />
        </div>
        <div>
          <label htmlFor="review-text" className="block text-xs font-medium text-slate-300 mb-1">Review text <span aria-hidden="true">*</span></label>
          <textarea
            id="review-text"
            value={reviewText}
            onChange={(event) => setReviewText(event.target.value)}
            required
            rows={5}
            maxLength={10000}
            placeholder="Share an employee experience, including details that may help assess it."
            className="w-full resize-y bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none"
          />
          <p className="text-right text-[11px] text-slate-500 mt-1" aria-live="polite">{reviewText.length}/10000</p>
        </div>
        <details className="group">
          <summary className="cursor-pointer text-xs text-cyan-300 hover:text-cyan-200">Add optional source and role details</summary>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
            {[
              ['source_type', 'Source type', 'e.g. review site, survey'],
              ['source_name', 'Source name', 'e.g. site or publication'],
              ['source_url', 'Source URL', 'https://...'],
              ['role', 'Role', 'e.g. Software Engineer'],
              ['location', 'Location', 'City, region'],
            ].map(([field, label, placeholder]) => (
              <div key={field}>
                <label htmlFor={`review-${field}`} className="block text-xs text-slate-400 mb-1">{label}</label>
                <input
                  id={`review-${field}`}
                  type={field === 'source_url' ? 'url' : 'text'}
                  value={metadata[field]}
                  onChange={updateMetadata(field)}
                  placeholder={placeholder}
                  className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
                />
              </div>
            ))}
            <div>
              <label htmlFor="review-date" className="block text-xs text-slate-400 mb-1">Review date</label>
              <input
                id="review-date"
                type="date"
                value={metadata.review_date}
                onChange={updateMetadata('review_date')}
                className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 outline-none"
              />
            </div>
          </div>
        </details>

        {error && <p role="alert" className="rounded border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300">{error}</p>}
        <button
          type="submit"
          disabled={loading || !companyName.trim() || !reviewText.trim()}
          className="px-4 py-2 rounded text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 disabled:opacity-60 disabled:cursor-not-allowed text-white transition-all inline-flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" aria-hidden="true" />
          {loading ? 'Analyzing review…' : 'Analyze review credibility'}
        </button>
      </form>

      {loading && <p role="status" className="text-xs text-cyan-300">Assessing credibility and extracting claims…</p>}
      {result && !loading && <ReviewResult result={result} />}
    </section>
  );
}
