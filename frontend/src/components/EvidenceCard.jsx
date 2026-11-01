import React from 'react';
import { 
  Cpu, 
  BrainCircuit, 
  AlertOctagon, 
  UserCheck, 
  Building2, 
  Globe, 
  Network, 
  DollarSign,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle
} from 'lucide-react';

const CATEGORY_ICONS = {
  ml: Cpu,
  transformer: BrainCircuit,
  scam: AlertOctagon,
  recruiter: UserCheck,
  company: Building2,
  website: Globe,
  domain: Network,
  salary: DollarSign,
};

export default function EvidenceCard({
  category = 'ml',
  title,
  status = 'unknown',
  score = 0,
  confidence = 0,
  explanation = 'No explanation provided.',
  signals = []
}) {
  const Icon = CATEGORY_ICONS[category.toLowerCase()] || Cpu;

  const normalizedStatus = (status || 'unknown').toLowerCase();
  
  let statusBadge = {
    label: 'Unknown',
    badgeClass: 'bg-slate-800 text-slate-300 border-slate-700',
    icon: HelpCircle,
    color: 'text-slate-400'
  };

  if (['verified', 'positive', 'safe', 'low_risk', 'legitimate'].includes(normalizedStatus)) {
    statusBadge = {
      label: 'Verified',
      badgeClass: 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30',
      icon: CheckCircle2,
      color: 'text-emerald-400'
    };
  } else if (['suspicious', 'negative', 'fraudulent', 'high_risk', 'anomalous'].includes(normalizedStatus)) {
    statusBadge = {
      label: 'Suspicious',
      badgeClass: 'bg-rose-950/40 text-rose-400 border-rose-500/30',
      icon: XCircle,
      color: 'text-rose-400'
    };
  } else if (['partially_verified', 'uncertain', 'warning', 'mixed', 'needs_verification', 'needs verification'].includes(normalizedStatus)) {
    statusBadge = {
      label: 'Needs Verification',
      badgeClass: 'bg-amber-950/40 text-amber-400 border-amber-500/30',
      icon: AlertTriangle,
      color: 'text-amber-400'
    };
  } else if (normalizedStatus === 'unavailable') {
    statusBadge = {
      label: 'Unavailable',
      badgeClass: 'bg-slate-800 text-slate-400 border-slate-700',
      icon: HelpCircle,
      color: 'text-slate-400'
    };
  }

  const StatusIcon = statusBadge.icon;

  return (
    <div className="bg-shield-card border border-shield-border hover:border-slate-700 rounded-lg p-5 flex flex-col justify-between transition-all">
      <div>
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded bg-shield-surface border border-shield-border text-cyan-400">
              <Icon className="w-4 h-4" />
            </div>
            <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
          </div>
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${statusBadge.badgeClass}`}>
            <StatusIcon className="w-3 h-3" />
            <span>{statusBadge.label}</span>
          </span>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed min-h-[36px]">{explanation}</p>

        {signals && signals.length > 0 && (
          <div className="mt-3 pt-3 border-t border-shield-border/60">
            <div className="text-[11px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">Detected Signals:</div>
            <ul className="space-y-1">
              {signals.slice(0, 3).map((sig, idx) => (
                <li key={idx} className="text-xs text-slate-400 flex items-start gap-1.5">
                  <span className="text-cyan-400 text-xs mt-0.5">•</span>
                  <span>{sig}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-4 pt-3 border-t border-shield-border flex items-center justify-between text-xs text-slate-400">
        <span className="font-mono">
          Score: <span className="text-slate-200 font-semibold">{typeof score === 'number' ? (score > 0 ? `+${score.toFixed(2)}` : score.toFixed(2)) : '0.00'}</span>
        </span>
        <span className="font-mono">
          Confidence: <span className="text-cyan-400 font-semibold">{Math.round((confidence || 0) * 100)}%</span>
        </span>
      </div>
    </div>
  );
}
