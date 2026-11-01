import React from 'react';
import { ShieldCheck, AlertTriangle, ShieldAlert, HelpCircle } from 'lucide-react';

export default function RiskBadge({ riskLevel, className = '' }) {
  const normalized = (riskLevel || '').toLowerCase().trim();

  let config = {
    label: 'Unknown',
    bg: 'bg-slate-800/80',
    border: 'border-slate-700',
    text: 'text-slate-300',
    dot: 'bg-slate-400',
    icon: HelpCircle
  };

  if (normalized.includes('legitimate') || normalized === 'low' || normalized === 'safe') {
    config = {
      label: 'Likely Legitimate',
      bg: 'bg-emerald-950/40',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400',
      dot: 'bg-emerald-400',
      icon: ShieldCheck
    };
  } else if (normalized.includes('needs verification') || normalized.includes('uncertain') || normalized === 'medium' || normalized === 'moderate') {
    config = {
      label: 'Needs Verification',
      bg: 'bg-amber-950/40',
      border: 'border-amber-500/30',
      text: 'text-amber-400',
      dot: 'bg-amber-400',
      icon: AlertTriangle
    };
  } else if (normalized.includes('fraudulent') || normalized === 'high' || normalized === 'scam') {
    config = {
      label: 'Likely Fraudulent',
      bg: 'bg-rose-950/40',
      border: 'border-rose-500/30',
      text: 'text-rose-400',
      dot: 'bg-rose-400',
      icon: ShieldAlert
    };
  }

  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border ${config.bg} ${config.border} ${config.text} ${className}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      <Icon className="w-3.5 h-3.5" />
      <span>{config.label}</span>
    </span>
  );
}
