import React, { useMemo, useState } from 'react';
import { api } from '../services/api';

const CATEGORY_COPY = {
  company_reputation: 'Company reputation',
  website_domain: 'Website and domain',
  recruiter: 'Recruiter verification',
  salary: 'Salary verification',
};

function formatValue(value) {
  return value || 'Not available';
}

function statusStyle(status) {
  if (status === 'Verified') return 'text-emerald-300';
  if (status === 'Unverified') return 'text-rose-300';
  if (status === 'Unavailable') return 'text-amber-300';
  return 'text-slate-300';
}

export default function ExternalVerificationConsent({ verification, onUpdate }) {
  const [current, setCurrent] = useState(verification);
  const [selected, setSelected] = useState(() => verification?.selected_checks || []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const checks = current?.checks || {};
  const details = current?.details || {};
  const frozen = ['consented', 'declined', 'running', 'completed', 'partial', 'failed'].includes(
    current?.consent_status,
  );
  const approvedChecks = useMemo(
    () => selected.map((key) => CATEGORY_COPY[key]).filter(Boolean),
    [selected],
  );

  if (!current?.analysis_id) return null;

  const update = (next) => {
    setCurrent(next);
    onUpdate?.(next);
  };

  const toggle = (key) => {
    setSelected((previous) => (
      previous.includes(key)
        ? previous.filter((item) => item !== key)
        : [...previous, key]
    ));
  };

  const approveChecks = async () => {
    setError('');
    if (!selected.length) {
      setError('Select at least one available check, or continue without verification.');
      return;
    }
    const disclosures = selected.flatMap((key) => checks[key]?.information_shared || []);
    const localDisclosures = selected.flatMap((key) => checks[key]?.processed_locally || []);
    const confirmation = [
      `Approve these checks for this analysis only: ${approvedChecks.join(', ')}.`,
      disclosures.length
        ? `Information sent to external services: ${[...new Set(disclosures)].join(', ')}.`
        : 'No information from the selected checks will be sent to external services.',
      localDisclosures.length
        ? `Information processed locally only: ${[...new Set(localDisclosures)].join(', ')}.`
        : '',
      'The complete email body and attachments will not be sent.',
    ].filter(Boolean).join('\n\n');
    if (!window.confirm(confirmation)) return;

    setBusy(true);
    try {
      const saved = await api.saveExternalVerificationConsent(
        current.analysis_id,
        true,
        selected,
      );
      update(saved);
    } catch (requestError) {
      setError(requestError.message || 'Could not save your consent.');
    } finally {
      setBusy(false);
    }
  };

  const runChecks = async () => {
    setError('');
    const retrying = ['failed', 'partial'].includes(current.consent_status);
    const checksToRun = retrying
      ? current.selected_checks.filter((key) => (
        !checks[key]?.result || checks[key]?.result?.status === 'Unavailable'
      ))
      : current.selected_checks;
    if (!checksToRun.length) {
      setError('There are no unfinished or unavailable checks to retry.');
      return;
    }
    const disclosures = checksToRun
      .flatMap((key) => checks[key]?.information_shared || []);
    const localDisclosures = checksToRun
      .flatMap((key) => checks[key]?.processed_locally || []);
    const confirmation = [
      `${retrying ? 'Retry only' : 'Run only'} the checks approved for this analysis: ${checksToRun.map((key) => CATEGORY_COPY[key]).join(', ')}.`,
      disclosures.length
        ? `Information sent to external services: ${[...new Set(disclosures)].join(', ')}.`
        : 'No information from the selected checks will be sent to external services.',
      localDisclosures.length
        ? `Information processed locally only: ${[...new Set(localDisclosures)].join(', ')}.`
        : '',
      retrying
        ? 'Previously saved successful results will not be requested again. A repeated provider request is possible only for a result that was not saved before an interruption.'
        : '',
      'The complete email body and attachments will not be sent.',
    ].filter(Boolean).join('\n\n');
    if (!window.confirm(confirmation)) return;

    setBusy(true);
    try {
      update(await api.runExternalVerification(current.analysis_id));
    } catch (requestError) {
      setError(requestError.message || 'External verification could not be completed.');
    } finally {
      setBusy(false);
    }
  };

  const refreshRunStatus = async () => {
    setError('');
    setBusy(true);
    try {
      update(await api.getExternalVerificationStatus(current.analysis_id));
    } catch (requestError) {
      setError(requestError.message || 'Could not refresh verification status.');
    } finally {
      setBusy(false);
    }
  };

  const decline = async () => {
    setError('');
    setBusy(true);
    try {
      update(await api.saveExternalVerificationConsent(current.analysis_id, false, []));
      setSelected([]);
    } catch (requestError) {
      setError(requestError.message || 'Could not record your choice.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-5 rounded-lg border border-cyan-500/25 bg-shield-card p-5">
      <div>
        <h3 className="text-base font-semibold text-slate-100">
          External Verification – Your Permission Required
        </h3>
        <p className="mt-2 text-sm text-slate-300">
          CareerShield completed private email analysis. You can approve specific checks below.
          Only the listed details for selected checks may be sent to their verification services.
          The complete email body and attachments are never sent.
        </p>
        <p className="mt-2 text-xs text-slate-400">
          Consent applies only to analysis {current.analysis_id}; it does not authorize checks on
          other analyses.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {[
          ['Company', details.company_name],
          ['Website URL', details.company_website],
          ['Recruiter email domain', details.recruiter_email_domain],
          ['Recruiter name', details.recruiter_name],
          ['Job title', details.job_title],
          ['Location', details.location],
          ['Salary information', details.salary],
        ].map(([label, value]) => (
          <div key={label} className="rounded border border-shield-border bg-shield-surface p-3">
            <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
            <div className="mt-1 break-words text-sm text-slate-200">{formatValue(value)}</div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        {Object.entries(CATEGORY_COPY).map(([key, label]) => {
          const item = checks[key] || {};
          const localValues = item.processed_locally || [];
          const externalValues = item.information_shared || [];
          return (
            <label
              key={key}
              className={`block rounded border border-shield-border bg-shield-surface p-3 ${
                item.available ? 'cursor-pointer' : 'cursor-not-allowed opacity-60'
              }`}
            >
              <span className="flex items-start gap-3">
                <input
                  type="checkbox"
                  className="mt-1 accent-cyan-500"
                  checked={selected.includes(key)}
                  disabled={!item.available || frozen || busy}
                  onChange={() => toggle(key)}
                />
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-slate-100">{label}</span>
                    <span className={`text-xs ${statusStyle(item.status)}`}>{item.status || 'Pending'}</span>
                  </span>
                  <span className="mt-1 block text-xs text-slate-400">
                    {key === 'company_reputation'
                      ? 'Public search uses the company name; the listing domain is compared locally.'
                      : key === 'website_domain'
                        ? 'Company website is checked when available; otherwise the recruiter domain is used for the domain check.'
                        : key === 'recruiter'
                          ? 'Recruiter and company domains are compared locally; no external request is made.'
                          : 'Salary realism is evaluated locally; no salary details are sent to a third party.'}
                  </span>
                  {externalValues.length > 0 && (
                    <span className="mt-2 block text-[11px] text-slate-300">
                      Sent externally: {externalValues.join(', ')}
                    </span>
                  )}
                  {localValues.length > 0 && (
                    <span className="mt-2 block text-[11px] text-slate-300">
                      Processed locally only: {localValues.join(', ')}
                    </span>
                  )}
                  {!externalValues.length && !localValues.length && (
                    <span className="mt-2 block text-[11px] text-slate-300">
                      {item.available
                        ? 'No data is shared until you approve and run this check.'
                        : item.reason}
                    </span>
                  )}
                </span>
              </span>
            </label>
          );
        })}
      </div>

      {current.consent_status === 'required' && (
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={approveChecks}
            disabled={busy || selected.length === 0}
            className="rounded bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? 'Saving consent…' : 'Approve Selected Checks'}
          </button>
          <button
            type="button"
            onClick={decline}
            disabled={busy}
            className="rounded border border-shield-border px-4 py-2 text-sm text-slate-200 hover:bg-shield-surface disabled:opacity-50"
          >
            Continue Without External Verification
          </button>
        </div>
      )}

      {current.consent_status === 'consented' && (
        <button
          type="button"
          onClick={runChecks}
          disabled={busy}
          className="rounded bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
        >
          {busy ? 'Running approved checks…' : 'Run Approved Checks'}
        </button>
      )}

      {current.consent_status === 'running' && (
        <button
          type="button"
          onClick={refreshRunStatus}
          disabled={busy}
          className="rounded border border-shield-border px-4 py-2 text-sm text-slate-200 hover:bg-shield-surface disabled:opacity-50"
        >
          {busy ? 'Checking status…' : 'Check run status'}
        </button>
      )}

      {['failed', 'partial'].includes(current.consent_status) && current.can_retry && (
        <div className="space-y-2">
          <p className="text-xs text-amber-300">
            Retry is limited to checks without a saved result or marked unavailable. Previously
            saved results will not be requested again; a provider response lost before saving may
            be requested once more.
          </p>
          <button
            type="button"
            onClick={runChecks}
            disabled={busy}
            className="rounded bg-cyan-600 px-4 py-2 text-sm font-semibold text-white hover:bg-cyan-500 disabled:opacity-50"
          >
            {busy ? 'Retrying approved checks…' : 'Retry remaining checks'}
          </button>
        </div>
      )}

      {current.consent_status === 'declined' && (
        <p className="text-sm text-slate-300">
          External checks were declined. The private analysis remains unchanged.
        </p>
      )}
      {current.consent_status === 'running' && (
        <p className="text-sm text-amber-300">Approved checks are marked as running.</p>
      )}
      {['completed', 'partial', 'failed'].includes(current.consent_status) && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-slate-100">Verification results</h4>
          {Object.entries(CATEGORY_COPY).map(([key, label]) => {
            const result = checks[key]?.result;
            if (!result) return null;
            return (
              <article key={key} className="rounded border border-shield-border bg-shield-surface p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h5 className="text-sm font-medium text-slate-100">{label}</h5>
                  <span className={`text-xs ${statusStyle(result.status)}`}>{result.status}</span>
                </div>
                {result.explanation && (
                  <p className="mt-2 text-xs text-slate-300">{result.explanation}</p>
                )}
                {result.evidence?.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-400">
                    {result.evidence.map((evidence, index) => <li key={index}>{evidence}</li>)}
                  </ul>
                )}
                {result.source && <p className="mt-2 text-[11px] text-slate-500">Source: {result.source}</p>}
                {result.confidence != null && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Confidence: {Math.round(Number(result.confidence) * 100)}%
                  </p>
                )}
                {result.retrieved_at && (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Checked: {new Date(result.retrieved_at).toLocaleString()}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}

      {error && <p role="alert" className="text-sm text-rose-300">{error}</p>}
    </section>
  );
}
