import React from 'react';
import { 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  HelpCircle, 
  MessageSquare,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';

export default function ClaimCard({ claimData }) {
  if (!claimData) return null;

  const {
    claim,
    aspect,
    sentiment,
    evidence_status = 'Insufficient Evidence',
    confidence = 0,
    supporting_evidence = [],
    contradicting_evidence = [],
    total_relevant_reviews = 0,
    explanation = ''
  } = claimData;

  const getStatusConfig = (status) => {
    switch ((status || '').toLowerCase()) {
      case 'supported':
        return {
          label: 'Supported',
          bg: 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30',
          icon: CheckCircle2,
          border: 'border-emerald-500/30'
        };
      case 'partially supported':
      case 'partially_supported':
        return {
          label: 'Partially Supported',
          bg: 'bg-amber-950/40 text-amber-400 border-amber-500/30',
          icon: AlertTriangle,
          border: 'border-amber-500/30'
        };
      case 'contradicted':
        return {
          label: 'Contradicted',
          bg: 'bg-rose-950/40 text-rose-400 border-rose-500/30',
          icon: XCircle,
          border: 'border-rose-500/30'
        };
      case 'unverified':
        return {
          label: 'Unverified',
          bg: 'bg-slate-800 text-slate-300 border-slate-700',
          icon: HelpCircle,
          border: 'border-slate-700'
        };
      case 'insufficient evidence':
      case 'insufficient_evidence':
      default:
        return {
          label: 'Insufficient Evidence',
          bg: 'bg-slate-800 text-slate-400 border-slate-700',
          icon: HelpCircle,
          border: 'border-slate-800'
        };
    }
  };

  const statusConfig = getStatusConfig(evidence_status);
  const StatusIcon = statusConfig.icon;

  return (
    <div className={`bg-shield-card border ${statusConfig.border} rounded-lg p-5 transition-all shadow-sm`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pb-3 border-b border-shield-border/60">
        <div>
          <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1 flex items-center gap-2">
            <span>Investigated Claim</span>
            {aspect && <span className="text-cyan-400">• Aspect: {aspect}</span>}
          </div>
          <div className="text-base font-semibold text-slate-100 flex items-start gap-2">
            <MessageSquare className="w-4 h-4 text-cyan-400 mt-1 shrink-0" />
            <span>"{claim}"</span>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium border ${statusConfig.bg}`}>
            <StatusIcon className="w-3.5 h-3.5" />
            <span>{statusConfig.label}</span>
          </span>
        </div>
      </div>

      {explanation && (
        <div className="mt-3 text-xs text-slate-300 leading-relaxed bg-shield-surface/60 p-3 rounded border border-shield-border/40">
          <span className="font-semibold text-slate-200">Synthesis: </span>
          {explanation}
        </div>
      )}

      {/* Supporting vs Contradicting Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
        {/* Supporting Evidence */}
        <div className="bg-shield-surface border border-shield-border p-3.5 rounded">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
              <ThumbsUp className="w-3.5 h-3.5" /> Supporting Evidence ({supporting_evidence.length})
            </span>
          </div>
          {supporting_evidence.length > 0 ? (
            <ul className="space-y-1.5">
              {supporting_evidence.map((ev, i) => (
                <li key={i} className="text-xs text-slate-300 flex items-start gap-1.5 bg-shield-card p-2 rounded border border-shield-border/50">
                  <span className="text-emerald-400 text-xs mt-0.5">•</span>
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-400 italic">No direct supporting evidence found in reviewed records.</p>
          )}
        </div>

        {/* Contradicting Evidence */}
        <div className="bg-shield-surface border border-shield-border p-3.5 rounded">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-rose-400 flex items-center gap-1.5">
              <ThumbsDown className="w-3.5 h-3.5" /> Contradicting Evidence ({contradicting_evidence.length})
            </span>
          </div>
          {contradicting_evidence.length > 0 ? (
            <ul className="space-y-1.5">
              {contradicting_evidence.map((ev, i) => (
                <li key={i} className="text-xs text-slate-300 flex items-start gap-1.5 bg-shield-card p-2 rounded border border-shield-border/50">
                  <span className="text-rose-400 text-xs mt-0.5">•</span>
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-slate-400 italic">No contradicting statements recorded in dataset.</p>
          )}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-shield-border/60 flex flex-wrap items-center justify-between text-xs text-slate-400 font-mono gap-2">
        <span>Relevant Reviews Analyzed: <span className="text-slate-200 font-semibold">{total_relevant_reviews}</span></span>
        <span>Decision Confidence: <span className="text-cyan-400 font-semibold">{Math.round(confidence * 100)}%</span></span>
        <span className="text-[11px] text-slate-400 font-sans italic">Decision support assessment, not an absolute truth determination.</span>
      </div>
    </div>
  );
}
