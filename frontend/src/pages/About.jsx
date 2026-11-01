import React from 'react';
import { 
  Shield, 
  Cpu, 
  Binary, 
  AlertTriangle, 
  CheckCircle2, 
  GitBranch,
  BookOpen
} from 'lucide-react';

export default function About() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header Card */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/30">
            System Whitepaper
          </span>
          <span className="text-xs text-slate-400">• Version 1.0</span>
        </div>
        <h2 className="text-xl font-bold text-slate-100">
          CareerShield – Framework Architecture & Decision Support Methodology
        </h2>
        <p className="text-xs text-slate-300 mt-1 leading-relaxed">
          An explainable, multi-evidence AI framework for recruitment fraud detection and independent company reputation assessment.
        </p>
      </div>

      {/* Core Purpose & Dual-Axis Vision */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-shield-card border border-shield-border rounded-lg p-5">
          <h3 className="text-sm font-semibold text-cyan-400 mb-2 flex items-center gap-2">
            <Shield className="w-4 h-4" /> Area 1: Recruitment Fraud Detection
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Identifies deceptive job postings, phishing hooks, fake interviews, fee extraction schemes, and unauthorized recruiter impersonation. Uses a multi-agent evidence fusion engine cross-checking linguistic cues, DNS MX validation, domain consistency, and salary benchmarks.
          </p>
          <div className="mt-3 p-2.5 rounded bg-shield-surface border border-shield-border text-[11px] text-slate-400">
            <strong className="text-slate-200">Goal: </strong> Protect job seekers from financial theft, identity theft, and counterfeit recruitment.
          </div>
        </div>

        <div className="bg-shield-card border border-shield-border rounded-lg p-5">
          <h3 className="text-sm font-semibold text-emerald-400 mb-2 flex items-center gap-2">
            <Cpu className="w-4 h-4" /> Area 2: Company Reputation & Claims
          </h3>
          <p className="text-xs text-slate-300 leading-relaxed">
            Evaluates genuine workplace sentiment across 9 structured aspects (work-life balance, management, career growth, compensation, culture, etc.) from verified employee reviews. Validates public claims without labeling unverified rumors as absolute fact.
          </p>
          <div className="mt-3 p-2.5 rounded bg-shield-surface border border-shield-border text-[11px] text-slate-400">
            <strong className="text-slate-200">Decoupling Principle: </strong> Recruitment Risk ≠ Company Reputation. Impersonators target great firms; legitimate firms may have workplace flaws.
          </div>
        </div>
      </div>

      {/* Mathematical Formulation Card */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <h3 className="text-sm font-semibold text-slate-100 mb-2 flex items-center gap-2">
          <Binary className="w-4 h-4 text-cyan-400" /> Evidence Fusion & Trust Score Formulation
        </h3>
        <p className="text-xs text-slate-300 leading-relaxed mb-4">
          Rather than relying on an opaque black-box neural probability, CareerShield computes a normalized multi-evidence fusion index:
        </p>

        <div className="bg-shield-surface border border-shield-border rounded-lg p-4 font-mono text-xs space-y-3">
          <div className="text-cyan-400 font-bold">
            Ef = Σ(wi × qi × ei) / Σ(wi × qi)
          </div>
          <div className="text-slate-300">
            Trust Score (TS) = 50 + 50 × Ef &nbsp;&nbsp;(Bounded: [0, 100])
          </div>
          <div className="text-[11px] text-slate-400 space-y-1 pt-2 border-t border-shield-border">
            <div>• <span className="text-slate-200">wi</span> : Pre-calibrated agent weight (e.g. upfront fee scam signal has high weight).</div>
            <div>• <span className="text-slate-200">qi</span> : Agent observation confidence / evidence quality in [0, 1].</div>
            <div>• <span className="text-slate-200">ei</span> : Directional evidence state score (-1 = severe fraud anomaly, 0 = unknown/neutral, +1 = verified legitimate).</div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 text-xs font-mono">
          <div className="p-3 rounded bg-emerald-950/30 border border-emerald-500/30">
            <div className="text-emerald-400 font-bold">75 – 100 : Likely Legitimate</div>
            <div className="text-[10px] text-slate-400 mt-1">Multi-evidence verifies entity consistency with absence of red flags.</div>
          </div>
          <div className="p-3 rounded bg-amber-950/30 border border-amber-500/30">
            <div className="text-amber-400 font-bold">50 – 74 : Needs Verification</div>
            <div className="text-[10px] text-slate-400 mt-1">Sparse external records or minor signal discrepancies requiring caution.</div>
          </div>
          <div className="p-3 rounded bg-rose-950/30 border border-rose-500/30">
            <div className="text-rose-400 font-bold">0 – 49 : Likely Fraudulent</div>
            <div className="text-[10px] text-slate-400 mt-1">Explicit scam triggers, payment demands, or fraudulent identity anomalies.</div>
          </div>
        </div>
      </div>

      {/* Fundamental System Axioms */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <h3 className="text-sm font-semibold text-slate-100 mb-3 flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-cyan-400" /> Core Ethical & Operational Axioms
        </h3>
        <div className="space-y-3 text-xs">
          <div className="p-3 rounded bg-shield-surface border border-shield-border flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <div>
              <strong className="text-slate-200">The Unknown Rule: </strong>
              If a small business lacks DNS MX records, career portal integration, or extensive online footprint, it is classified as <span className="text-slate-300 font-mono">Unknown / Insufficient Evidence</span>, never automatically marked as fraudulent.
            </div>
          </div>

          <div className="p-3 rounded bg-shield-surface border border-shield-border flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <div>
              <strong className="text-slate-200">The Corroboration Rule: </strong>
              A single negative review or isolated allegation does NOT prove a claim. Public claims require independent repetitions, aspect alignment, and contradiction checking before being categorized as Supported or Contradicted.
            </div>
          </div>

          <div className="p-3 rounded bg-shield-surface border border-shield-border flex items-start gap-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
            <div>
              <strong className="text-slate-200">Graceful Neural Degradation: </strong>
              If the Hugging Face transformer API is unreachable or tokens are omitted, the local supervised NLP model and rule-based heuristic agents maintain continuous decision support without application failure.
            </div>
          </div>
        </div>
      </div>

      {/* Limitations & Future Work */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-shield-card border border-shield-border rounded-lg p-5">
          <h3 className="text-sm font-semibold text-amber-400 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" /> Current Limitations
          </h3>
          <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
            <li>Zero-day typosquatted domains might briefly slip past standard WHOIS throttling.</li>
            <li>Review corpora may reflect historical corporate culture that has since improved or changed.</li>
            <li>Adversarial job descriptions crafted by advanced LLMs require continuous model updates.</li>
          </ul>
        </div>

        <div className="bg-shield-card border border-shield-border rounded-lg p-5">
          <h3 className="text-sm font-semibold text-cyan-400 mb-2 flex items-center gap-2">
            <GitBranch className="w-4 h-4" /> Future Roadmap
          </h3>
          <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
            <li>Browser extension for automated real-time LinkedIn, Indeed, and Telegram inspection.</li>
            <li>Decentralized cryptographic credential verification for recruiters (DID/W3C).</li>
            <li>Real-time fine-tuned RoBERTa models deployed on isolated GPU inference clusters.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
