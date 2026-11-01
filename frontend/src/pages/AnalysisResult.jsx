import React from 'react';
import { 
  ArrowLeft, 
  Building, 
  CheckCircle2, 
  XCircle, 
  HelpCircle,
  Hash,
  Clock,
  Sparkles,
  ExternalLink
} from 'lucide-react';
import TrustScore from '../components/TrustScore';
import RiskBadge from '../components/RiskBadge';
import EvidenceCard from '../components/EvidenceCard';
import EvidenceChart from '../components/EvidenceChart';
import ExternalVerificationConsent from '../components/ExternalVerificationConsent';

export default function AnalysisResult({ result, onBack, onInspectCompany, onVerificationUpdate }) {
  if (!result) {
    return (
      <div className="text-center py-16">
        <p className="text-sm text-slate-400">No analysis result loaded.</p>
        <button
          onClick={onBack}
          className="mt-4 px-4 py-2 rounded text-xs bg-cyan-600 text-white"
        >
          Back to Analyzer
        </button>
      </div>
    );
  }

  const {
    id,
    job_title,
    company_name,
    trust_score = 50,
    risk_level = 'Needs Verification',
    fraud_probability = 0,
    confidence = 0,
    created_at,
    positive_evidence = [],
    negative_evidence = [],
    unknown_evidence = [],
    evidence_contributions = [],
    evidence_details = {},
    advanced_ai_analysis = {},
    recruiter_result = {},
    company_result = {},
    website_result = {},
    domain_result = {},
    salary_result = {},
    transformer_result = {},
    ml_result = {},
    external_verification = {}
  } = result;

  // Build 8 distinct evidence cards for Section 11
  const evidenceCards = [
    {
      category: 'ml',
      title: 'Job ML Classifier',
      status: ml_result.status || 'verified',
      score: ml_result.score || 0,
      confidence: ml_result.confidence || confidence,
      explanation: ml_result.explanation || `TF-IDF + Logistic Regression evaluated job posting language. Fraud probability: ${Math.round((fraud_probability || 0) * 100)}%.`,
      signals: ml_result.signals || []
    },
    {
      category: 'transformer',
      title: 'Transformer API',
      status: transformer_result.status || 'unavailable',
      score: transformer_result.score || 0,
      confidence: transformer_result.confidence || 0,
      explanation: transformer_result.explanation || (transformer_result.status === 'unavailable' ? 'Hugging Face inference API token not configured or endpoint unavailable. Fallback to local intelligence.' : 'Transformer evaluated semantic linguistic consistency.'),
      signals: transformer_result.signals || []
    },
    {
      category: 'scam',
      title: 'Scam Signals Agent',
      status: negative_evidence.length > 0 ? 'suspicious' : 'verified',
      score: negative_evidence.length > 0 ? -0.8 : 0.8,
      confidence: 0.9,
      explanation: negative_evidence.length > 0 ? `Detected ${negative_evidence.length} high-risk scam triggers or predatory clauses.` : 'No upfront payment, registration fee, or credential harvest patterns detected.',
      signals: negative_evidence.slice(0, 3)
    },
    {
      category: 'recruiter',
      title: 'Recruiter Verification',
      status: recruiter_result.status || 'unknown',
      score: recruiter_result.score || 0,
      confidence: recruiter_result.confidence || 0.7,
      explanation: recruiter_result.explanation || 'Recruiter identity and email domain audit.',
      signals: recruiter_result.signals || []
    },
    {
      category: 'company',
      title: 'Company Identity',
      status: company_result.status || 'unknown',
      score: company_result.score || 0,
      confidence: company_result.confidence || 0.7,
      explanation: company_result.explanation || 'Corporate profile and entity verification.',
      signals: company_result.signals || []
    },
    {
      category: 'website',
      title: 'Website Security Agent',
      status: website_result.status || 'unknown',
      score: website_result.score || 0,
      confidence: website_result.confidence || 0.6,
      explanation: website_result.explanation || 'SSL certificate, career page existence, and URL integrity.',
      signals: website_result.signals || []
    },
    {
      category: 'domain',
      title: 'Domain & DNS Agent',
      status: domain_result.status || 'unknown',
      score: domain_result.score || 0,
      confidence: domain_result.confidence || 0.7,
      explanation: domain_result.explanation || 'DNS A/MX records, email routing, and domain validation.',
      signals: domain_result.signals || []
    },
    {
      category: 'salary',
      title: 'Salary Realism Agent',
      status: salary_result.status || 'unknown',
      score: salary_result.score || 0,
      confidence: salary_result.confidence || 0.6,
      explanation: salary_result.explanation || 'Compensation range benchmarked against role expectations.',
      signals: salary_result.signals || []
    }
  ];

  return (
    <div className="space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-slate-400 hover:text-slate-200 border border-shield-border hover:bg-shield-surface transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Analyzer</span>
        </button>

        {company_name && onInspectCompany && (
          <button
            onClick={() => onInspectCompany(company_name)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-cyan-400 border border-cyan-500/30 bg-cyan-950/40 hover:bg-cyan-900/50 transition-colors"
          >
            <Building className="w-3.5 h-3.5" />
            <span>Inspect Company Reputation: {company_name}</span>
            <ExternalLink className="w-3 h-3" />
          </button>
        )}
      </div>

      {/* Primary Result Card */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center">
          {/* Circular Trust Score */}
          <div className="flex flex-col items-center justify-center p-4 border-b lg:border-b-0 lg:border-r border-shield-border">
            <TrustScore score={trust_score} size={170} />
            <div className="mt-3">
              <RiskBadge riskLevel={risk_level} />
            </div>
          </div>

          {/* Job Details & Metadata */}
          <div className="lg:col-span-2 space-y-4">
            <div>
              <div className="flex items-center gap-2 text-xs text-slate-400 font-mono mb-1">
                <span className="flex items-center gap-1">
                  <Hash className="w-3 h-3 text-cyan-400" /> ID: {id ? id.toString().slice(0, 8) : 'N/A'}
                </span>
                <span>•</span>
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3 text-slate-400" />
                  {created_at ? new Date(created_at).toLocaleString() : 'Just now'}
                </span>
              </div>
              <h2 className="text-xl font-bold text-slate-100">{job_title || 'Recruitment Position'}</h2>
              <div className="text-xs text-cyan-400 font-semibold mt-0.5">
                {company_name || 'Unspecified Organization'}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="bg-shield-surface border border-shield-border p-3 rounded">
                <div className="text-[11px] text-slate-400 uppercase font-mono">Evidence Findings</div>
                <div className="text-lg font-bold font-mono text-slate-100 mt-0.5">
                  {positive_evidence.length + negative_evidence.length + unknown_evidence.length}
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Across job and company signals</div>
              </div>

              <div className="bg-shield-surface border border-shield-border p-3 rounded">
                <div className="text-[11px] text-slate-400 uppercase font-mono">Overall Confidence</div>
                <div className="text-lg font-bold font-mono text-cyan-400 mt-0.5">
                  {Math.round((confidence || 0) * 100)}%
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">Multi-source evidence quality</div>
              </div>

              <div className="bg-shield-surface border border-shield-border p-3 rounded">
                <div className="text-[11px] text-slate-400 uppercase font-mono">Evidence Decoupling</div>
                <div className="text-xs font-semibold text-emerald-400 mt-1">Verified Separate</div>
                <div className="text-[10px] text-slate-400 mt-0.5">Risk != Workplace Reputation</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Explainability Section: Why this result? (Section 12) */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <h3 className="text-base font-semibold text-slate-100">Why this result? Explainable Evidence Breakdown</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Transparent justification of findings grouped by positive trust factors, negative risk flags, and unknown fields.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Positive Evidence */}
          <div className="bg-shield-surface border border-emerald-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-shield-border/60">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
                Positive Evidence ({positive_evidence.length})
              </h4>
            </div>
            {positive_evidence.length > 0 ? (
              <ul className="space-y-2">
                {positive_evidence.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2 bg-emerald-950/20 border border-emerald-500/20 p-2.5 rounded">
                    <span className="text-emerald-400 text-xs mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">No definitive positive signals recorded.</p>
            )}
          </div>

          {/* Negative Evidence */}
          <div className="bg-shield-surface border border-rose-500/20 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-shield-border/60">
              <XCircle className="w-4 h-4 text-rose-400" />
              <h4 className="text-xs font-semibold uppercase tracking-wider text-rose-400">
                Negative Evidence ({negative_evidence.length})
              </h4>
            </div>
            {negative_evidence.length > 0 ? (
              <ul className="space-y-2">
                {negative_evidence.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-300 flex items-start gap-2 bg-rose-950/20 border border-rose-500/20 p-2.5 rounded">
                    <span className="text-rose-400 text-xs mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">No red flags or fraud triggers detected.</p>
            )}
          </div>

          {/* Unknown Evidence */}
          <div className="bg-shield-surface border border-slate-700 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3 pb-2 border-b border-shield-border/60">
              <HelpCircle className="w-4 h-4 text-slate-400" />
              <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Unknown Evidence ({unknown_evidence.length})
              </h4>
            </div>
            {unknown_evidence.length > 0 ? (
              <ul className="space-y-2">
                {unknown_evidence.map((item, idx) => (
                  <li key={idx} className="text-xs text-slate-400 flex items-start gap-2 bg-slate-900/60 border border-slate-800 p-2.5 rounded">
                    <span className="text-slate-500 text-xs mt-0.5">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-400 italic">All analyzed dimensions provided clear evidence.</p>
            )}
            <div className="mt-3 pt-2 border-t border-shield-border/40 text-[10px] text-slate-400 italic">
              Note: Under CareerShield rules, unknown evidence does NOT automatically penalize the score as fraud.
            </div>
          </div>
        </div>
      </div>

      <ExternalVerificationConsent
        key={external_verification.analysis_id || id || 'no-analysis'}
        verification={external_verification}
        onUpdate={onVerificationUpdate}
      />

      <details className="bg-shield-card border border-shield-border rounded-lg p-4">
        <summary className="cursor-pointer list-none text-sm font-semibold text-cyan-400">
          Advanced AI Analysis
        </summary>
        <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-300">
          <div className="bg-shield-surface border border-shield-border rounded p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Model output</div>
            <ul className="space-y-1.5">
              <li><span className="text-slate-400">ML fraud probability:</span> {Math.round((ml_result.fraud_probability || 0) * 100)}%</li>
              <li><span className="text-slate-400">Model confidence:</span> {Math.round(((ml_result.confidence || confidence) || 0) * 100)}%</li>
              <li><span className="text-slate-400">Semantic model:</span> {transformer_result.status || 'Unavailable'}</li>
            </ul>
          </div>
          <div className="bg-shield-surface border border-shield-border rounded p-3">
            <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Fusion details</div>
            <ul className="space-y-1.5">
              <li><span className="text-slate-400">Evidence index:</span> {Number(evidence_details.evidence_index ?? 0).toFixed(3)}</li>
              <li><span className="text-slate-400">Signals evaluated:</span> {advanced_ai_analysis.total_signals_evaluated ?? evidence_contributions.length ?? 0}</li>
              <li><span className="text-slate-400">Contribution count:</span> {evidence_contributions.length}</li>
            </ul>
          </div>
          {advanced_ai_analysis.model_fusion && (
            <div className="md:col-span-2 bg-shield-surface border border-shield-border rounded p-3">
              <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-2">Evidence fusion weights</div>
              <div className="space-y-2">
                {Object.entries(advanced_ai_analysis.model_fusion.weights || {}).map(([key, value]) => (
                  <div key={key} className="flex justify-between gap-4 text-[11px]">
                    <span className="text-slate-300">{key}</span>
                    <span className="font-mono text-cyan-400">{Number(value).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="md:col-span-2">
            <EvidenceChart contributions={evidence_contributions} />
          </div>
        </div>
      </details>

      {/* Evidence Analysis 8 Cards Grid (Section 11) */}
      <div className="space-y-3">
        <div>
          <h3 className="text-base font-semibold text-slate-100">Evidence Analysis Details</h3>
          <p className="text-xs text-slate-400">Findings from recruiter, company, scam, website, domain, and salary checks</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {evidenceCards.filter((card) => !['ml', 'transformer'].includes(card.category)).map((card, idx) => (
            <EvidenceCard
              key={idx}
              category={card.category}
              title={card.title}
              status={card.status}
              score={card.score}
              confidence={card.confidence}
              explanation={card.explanation}
              signals={card.signals}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
