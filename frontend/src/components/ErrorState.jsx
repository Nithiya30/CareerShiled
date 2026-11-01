import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorState({ 
  title = 'Service Error', 
  message = 'An unexpected error occurred while communicating with the service.', 
  onRetry 
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center bg-rose-950/20 border border-rose-500/30 rounded-lg">
      <div className="p-3 rounded-full bg-rose-900/30 border border-rose-500/30 text-rose-400 mb-3">
        <AlertCircle className="w-6 h-6" />
      </div>
      <h3 className="text-base font-semibold text-rose-200">{title}</h3>
      <p className="text-xs text-rose-300/80 mt-1 max-w-md">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 inline-flex items-center gap-2 px-3.5 py-1.5 rounded-md text-xs font-medium bg-rose-600 hover:bg-rose-500 text-white transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}
