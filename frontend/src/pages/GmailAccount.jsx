import React, { useEffect, useState } from 'react';
import { Mail, ShieldCheck, ShieldOff } from 'lucide-react';
import api from '../services/api';

export default function GmailAccount() {
  const [connectionResult] = useState(
    () => new URL(window.location.href).searchParams.get('gmail_connection'),
  );
  const [account, setAccount] = useState(null);
  const [monitoring, setMonitoring] = useState(null);
  const [consentChecked, setConsentChecked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(
    connectionResult === 'failed'
      ? 'Gmail could not be connected. Check configuration and try again.'
      : '',
  );
  const [notice, setNotice] = useState(
    connectionResult === 'connected'
      ? 'Gmail is connected. Monitoring has not been enabled.'
      : connectionResult === 'cancelled'
        ? 'Google authorization was cancelled. No account was connected.'
        : '',
  );

  useEffect(() => {
    let active = true;
    const loadAccount = async () => {
      try {
        const [current, monitoringStatus] = await Promise.all([
          api.getGmailAccount(),
          api.getGmailMonitoringStatus(),
        ]);
        if (active) {
          setAccount(current);
          setMonitoring(monitoringStatus);
        }
      } catch {
        if (active) setError('Could not load Gmail connection status. Please try again.');
      } finally {
        if (active) setLoading(false);
      }
    };

    const url = new URL(window.location.href);
    if (connectionResult) {
      url.searchParams.delete('gmail_connection');
      window.history.replaceState({}, '', `${url.pathname}${url.search}`);
    }
    loadAccount();

    return () => {
      active = false;
    };
  }, [connectionResult]);

  const connect = async () => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api.startGmailOAuth();
      window.location.assign(result.authorization_url);
    } catch {
      setError('Could not start Google authorization. Check the backend configuration.');
      setBusy(false);
    }
  };

  const disconnect = async () => {
    if (!window.confirm('Disconnect this Gmail account from CareerShield?')) return;
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const result = await api.disconnectGmailAccount();
      setAccount({
        connected: false,
        status: 'disconnected',
        monitoring_enabled: false,
      });
      setMonitoring(null);
      setNotice(
        result.remote_revocation === 'confirmed'
          ? 'Gmail was disconnected and Google confirmed credential revocation.'
          : 'Gmail was disconnected locally. Google credential revocation could not be confirmed.',
      );
    } catch {
      setError('Could not disconnect Gmail. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const updateMonitoring = async (action) => {
    setBusy(true);
    setError('');
    setNotice('');
    try {
      const current = action === 'pause'
        ? await api.pauseGmailMonitoring()
        : action === 'resume'
          ? await api.resumeGmailMonitoring()
          : await api.enableGmailMonitoring();
      setMonitoring(current);
      setAccount((previous) => ({
        ...previous,
        monitoring_enabled: current.enabled,
      }));
      setConsentChecked(false);
      setNotice(
        action === 'pause'
          ? 'Gmail monitoring is paused. Messages received while paused will be skipped when you resume.'
          : action === 'resume'
            ? 'Gmail monitoring resumed from a fresh baseline. Earlier messages will not be scanned.'
            : 'Gmail monitoring is enabled from a fresh baseline. Earlier messages will not be scanned.',
      );
    } catch (requestError) {
      setError(
        requestError.status === 503
          ? 'Gmail monitoring is unavailable until the database migrations are applied and Google access is configured.'
          : 'Could not update Gmail monitoring. Reconnect Gmail if authorization has expired, then try again.',
      );
    } finally {
      setBusy(false);
    }
  };

  const connected = account?.connected === true;
  const reauthRequired = account?.status === 'reauth_required';
  const monitoringEnabled = monitoring?.enabled === true;
  const previouslyConsented = Boolean(monitoring?.consented_at);

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-cyan-500/30 bg-cyan-500/10 text-cyan-300">
          <Mail className="h-5 w-5" aria-hidden="true" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Gmail connection</h1>
          <p className="text-sm text-slate-400">Manage the Google account linked to CareerShield.</p>
        </div>
      </header>

      <div className="rounded-xl border border-shield-border bg-shield-surface p-5">
        {loading ? (
          <p className="text-sm text-slate-400">Loading connection status…</p>
        ) : (
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
              {connected
                ? <ShieldCheck className="mt-0.5 h-5 w-5 text-emerald-400" aria-hidden="true" />
                : <ShieldOff className="mt-0.5 h-5 w-5 text-slate-500" aria-hidden="true" />}
              <div>
                <p className="font-medium text-slate-100">
                  {connected ? account.gmail_address : 'No Gmail account connected'}
                </p>
                <p className="mt-1 text-sm text-slate-400">
                  {reauthRequired
                    ? 'Google authorization needs to be renewed.'
                    : connected
                      ? 'Connected · monitoring requires separate consent.'
                      : 'Connecting an account does not turn on email monitoring.'}
                </p>
              </div>
            </div>
            {connected && !reauthRequired ? (
              <button
                type="button"
                onClick={disconnect}
                disabled={busy}
                className="rounded-lg border border-rose-500/40 px-4 py-2 text-sm font-medium text-rose-300 hover:bg-rose-500/10 disabled:opacity-50"
              >
                {busy ? 'Disconnecting…' : 'Disconnect Gmail'}
              </button>
            ) : (
              <button
                type="button"
                onClick={connect}
                disabled={busy || loading}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
              >
                {busy ? 'Starting…' : reauthRequired ? 'Reconnect Gmail' : 'Connect Gmail'}
              </button>
            )}
          </div>
        )}
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5 text-sm text-amber-100">
        <h2 className="font-semibold">Read-only access and private triage</h2>
        <p className="mt-2 leading-6 text-amber-100/80">
          Connecting does not start monitoring. Monitoring requires the separate
          consent action below. CareerShield uses Gmail read-only access and
          analyzes eligible messages locally in private-email mode; message
          bodies are not retained, and external verification is skipped.
        </p>
        <p className="mt-2 leading-6 text-amber-100/80">
          Enabling or resuming establishes a new baseline, so older messages and
          messages received while paused are skipped. Gmail read-only access is a
          restricted Google scope; Google may require app verification and a
          security assessment before public production use.
        </p>
      </div>

      {connected && monitoring && (
        <div className="space-y-4 rounded-xl border border-shield-border bg-shield-surface p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-semibold text-slate-100">Automatic email monitoring</h2>
              <p className="mt-1 text-sm text-slate-400">
                Status: {monitoringEnabled ? 'On' : previouslyConsented ? 'Paused' : 'Off'}
                {monitoring.last_successful_sync_at
                  ? ` · Last sync ${new Date(monitoring.last_successful_sync_at).toLocaleString()}`
                  : ''}
              </p>
              {monitoring.last_error_code && (
                <p role="status" className="mt-1 text-sm text-amber-300">
                  Latest sync status: {monitoring.last_error_code.replaceAll('_', ' ')}.
                </p>
              )}
            </div>
            {monitoringEnabled ? (
              <button
                type="button"
                onClick={() => updateMonitoring('pause')}
                disabled={busy}
                className="rounded-lg border border-amber-500/40 px-4 py-2 text-sm font-medium text-amber-200 hover:bg-amber-500/10 disabled:opacity-50"
              >
                {busy ? 'Updating…' : 'Pause monitoring'}
              </button>
            ) : (
              <button
                type="button"
                onClick={() => updateMonitoring(previouslyConsented ? 'resume' : 'enable')}
                disabled={busy || reauthRequired || !consentChecked}
                className="rounded-lg bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
              >
                {busy
                  ? 'Updating…'
                  : reauthRequired
                    ? 'Reconnect Gmail to monitor'
                    : previouslyConsented
                      ? 'Resume monitoring'
                      : 'Enable monitoring'}
              </button>
            )}
          </div>
          {!monitoringEnabled && (
            <label className="flex items-start gap-3 text-sm leading-6 text-slate-300">
              <input
                type="checkbox"
                checked={consentChecked}
                onChange={(event) => setConsentChecked(event.target.checked)}
                className="mt-1 h-4 w-4 accent-cyan-500"
              />
              <span>
                I explicitly consent to monitoring new Gmail messages for recruitment
                risk. I understand CareerShield will retrieve new messages after the
                baseline, analyze content locally, and not retain full message bodies.
              </span>
            </label>
          )}
          <p className="text-xs text-slate-500">
            Scanned: {monitoring.scanned_count} · Risk items: {monitoring.suspicious_count}
          </p>
        </div>
      )}

      {notice && (
        <p role="status" className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-200">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-rose-500/30 bg-rose-950/20 px-4 py-3 text-sm text-rose-200">
          {error}
        </p>
      )}
    </section>
  );
}
