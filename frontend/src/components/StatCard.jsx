import React from 'react';

export default function StatCard({ title, value, subtitle, icon: Icon, color = 'cyan', badge }) {
  const colorMap = {
    cyan: 'text-cyan-400 bg-cyan-950/30 border-cyan-500/20',
    emerald: 'text-emerald-400 bg-emerald-950/30 border-emerald-500/20',
    amber: 'text-amber-400 bg-amber-950/30 border-amber-500/20',
    rose: 'text-rose-400 bg-rose-950/30 border-rose-500/20',
    blue: 'text-blue-400 bg-blue-950/30 border-blue-500/20',
    slate: 'text-slate-400 bg-slate-800/40 border-slate-700/50',
  };

  const selectedColor = colorMap[color] || colorMap.slate;

  return (
    <div className="bg-shield-card border border-shield-border hover:border-slate-700 rounded-lg p-5 transition-colors shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">{title}</span>
        {Icon && (
          <div className={`p-2 rounded-md border ${selectedColor}`}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold font-mono text-slate-100">{value}</span>
        {badge && <div>{badge}</div>}
      </div>
      {subtitle && <p className="text-xs text-slate-400 mt-2">{subtitle}</p>}
    </div>
  );
}
