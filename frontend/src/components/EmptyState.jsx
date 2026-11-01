import React from 'react';
import { Shield, ArrowRight } from 'lucide-react';

export default function EmptyState({ 
  icon: Icon = Shield, 
  title = 'No Data Available', 
  description = 'No records or analyses found matching your query.',
  actionText,
  onAction 
}) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center bg-shield-card/50 border border-shield-border rounded-lg">
      <div className="p-3.5 rounded-full bg-shield-surface border border-shield-border text-slate-400 mb-3">
        <Icon className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-slate-200">{title}</h3>
      <p className="text-xs text-slate-400 mt-1 max-w-md">{description}</p>
      {actionText && onAction && (
        <button
          onClick={onAction}
          className="mt-4 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium bg-cyan-600 hover:bg-cyan-500 text-white transition-colors"
        >
          <span>{actionText}</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}
