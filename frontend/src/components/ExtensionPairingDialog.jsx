import React, { useEffect, useState } from 'react';
import { Check, Copy, Puzzle, X } from 'lucide-react';
import api from '../services/api';

export default function ExtensionPairingDialog({ onClose }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    api.createExtensionPairing()
      .then((response) => {
        if (active) setCode(response.code);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message || 'Could not create an extension pairing code.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setError('Clipboard access is unavailable. Select and copy the code manually.');
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="extension-pair-title"
        className="w-full max-w-md rounded-xl border border-shield-border bg-shield-card p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-cyan-950/60 p-2 text-cyan-300">
              <Puzzle className="h-5 w-5" />
            </div>
            <div>
              <h2 id="extension-pair-title" className="text-base font-semibold text-slate-100">
                Connect the Gmail extension
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                Enter this one-time code in the CareerShield extension. It expires in 5 minutes.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close pairing dialog"
            className="rounded p-1 text-slate-400 hover:bg-shield-surface hover:text-slate-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {loading && <p className="mt-5 text-sm text-slate-300">Generating secure pairing code…</p>}
        {code && (
          <div className="mt-5 flex gap-2">
            <input
              readOnly
              value={code}
              aria-label="One-time extension pairing code"
              onFocus={(event) => event.target.select()}
              className="min-w-0 flex-1 select-all rounded-md border border-shield-border bg-shield-surface px-3 py-2 font-mono text-sm text-cyan-200"
            />
            <button
              type="button"
              onClick={copyCode}
              className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/40 px-3 py-2 text-xs text-cyan-200 hover:bg-cyan-950/40"
            >
              {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        )}
        {error && <p role="alert" className="mt-4 text-xs text-rose-300">{error}</p>}
        <p className="mt-4 text-[11px] leading-relaxed text-slate-500">
          The code is single-use. The extension receives a short-lived session token; your password is never entered or stored in the extension.
        </p>
      </section>
    </div>
  );
}
