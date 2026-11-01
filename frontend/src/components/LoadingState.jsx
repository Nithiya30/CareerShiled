import React from 'react';
import { Loader2 } from 'lucide-react';

export default function LoadingState({ message = 'Analyzing recruitment signals...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      <div className="relative mb-4">
        <div className="w-12 h-12 rounded-full border-2 border-shield-border border-t-cyan-400 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <Loader2 className="w-5 h-5 text-cyan-400 animate-spin" />
        </div>
      </div>
      <h3 className="text-base font-semibold text-slate-200">{message}</h3>
      <p className="text-xs text-slate-400 mt-1 max-w-sm">
        Querying machine learning models, external intelligence agents, and synthesizing evidence...
      </p>
    </div>
  );
}
