import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts';
import {
  Star,
  TrendingUp,
  Scale,
  Briefcase,
  ShieldCheck,
  Users,
  Heart,
  BookOpen,
  Clock,
  HelpCircle,
  AlertCircle
} from 'lucide-react';

const ASPECT_ICONS = {
  work_life_balance: Clock,
  salary_benefits: Briefcase,
  career_growth: TrendingUp,
  job_security: ShieldCheck,
  management: Users,
  work_satisfaction: Heart,
  skill_development: BookOpen,
  culture: Users,
  workload: Scale
};

const ASPECT_LABELS = {
  work_life_balance: 'Work-Life Balance',
  salary_benefits: 'Salary & Benefits',
  career_growth: 'Career Growth',
  job_security: 'Job Security',
  management: 'Management',
  work_satisfaction: 'Work Satisfaction',
  skill_development: 'Skill Development',
  culture: 'Culture',
  workload: 'Workload'
};

const asArray = (value) => (Array.isArray(value) ? value : value ? [value] : []);

const formatPercent = (value) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available';
  return `${Math.round(value <= 1 ? value * 100 : value)}%`;
};

const formatScore = (value) => (
  typeof value === 'number' && Number.isFinite(value)
    ? `${(value <= 1 ? value * 100 : value).toFixed(1)}/100`
    : 'Not available'
);

function evidenceText(item) {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return String(item ?? '');
  return item.evidence_text || item.text || item.description || item.title || JSON.stringify(item);
}

function countFor(counts, keys) {
  for (const key of keys) {
    if (typeof counts?.[key] === 'number') return counts[key];
  }
  return null;
}

function CountCard({ label, value, color }) {
  return (
    <div className="bg-shield-surface border border-shield-border rounded p-3">
      <span className="block text-[10px] text-slate-400 uppercase">{label}</span>
      <span className={`text-xl font-semibold ${color}`}>{value ?? 'Not available'}</span>
    </div>
  );
}

export default function CompanyReputation({ reputationData }) {
  if (!reputationData) {
    return (
      <div className="bg-shield-card border border-shield-border rounded-lg p-8 text-center">
        <HelpCircle className="w-8 h-8 text-slate-500 mx-auto mb-2" aria-hidden="true" />
        <p className="text-sm text-slate-400">Review dataset unavailable or no reviews found for this company.</p>
      </div>
    );
  }

  const {
    company_name: companyName,
    total_reviews: totalReviews,
    average_rating: averageRating,
    sentiment_distribution: sentimentDistributionValue,
    aspects: aspectsValue,
    dataset_available: datasetAvailable,
    confidence,
    credibility_score: credibilityScore,
    evidence_coverage: evidenceCoverage,
    credibility_counts: credibilityCounts,
    credibility_evidence: credibilityEvidence,
    credibility_limitations: credibilityLimitations,
    limitations
  } = reputationData;
  const sentimentDistribution = sentimentDistributionValue || {};
  const aspects = aspectsValue || {};
  const reviewCount = typeof totalReviews === 'number' ? totalReviews : 0;
  const hasLegacyReviewData = datasetAvailable !== false && reviewCount > 0;
  const sentimentData = [
    { name: 'Positive', count: sentimentDistribution.positive || 0, color: '#10B981' },
    { name: 'Neutral', count: sentimentDistribution.neutral || 0, color: '#64748B' },
    { name: 'Negative', count: sentimentDistribution.negative || 0, color: '#EF4444' }
  ];
  const credible = countFor(credibilityCounts, ['credible', 'credible_count', 'credible_reviews']);
  const needsVerification = countFor(credibilityCounts, ['needs_verification', 'needs_verification_count', 'needs_verification_reviews']);
  const suspicious = countFor(credibilityCounts, ['suspicious', 'suspicious_count', 'suspicious_reviews']);
  const hasCredibilitySummary = credibilityScore !== undefined || evidenceCoverage !== undefined || credibilityCounts !== undefined;
  const evidenceItems = asArray(credibilityEvidence ?? reputationData.evidence);
  const limitationItems = asArray(credibilityLimitations ?? limitations);

  const getAspectBadge = (state) => {
    switch ((state || '').toLowerCase()) {
      case 'positive':
        return { label: 'Positive', bg: 'bg-emerald-950/40 text-emerald-400 border-emerald-500/30' };
      case 'negative':
        return { label: 'Negative', bg: 'bg-rose-950/40 text-rose-400 border-rose-500/30' };
      case 'mixed':
        return { label: 'Mixed', bg: 'bg-amber-950/40 text-amber-400 border-amber-500/30' };
      default:
        return { label: 'Insufficient Evidence', bg: 'bg-slate-800 text-slate-400 border-slate-700' };
    }
  };

  return (
    <div className="space-y-6">
      <section className="bg-shield-card border border-shield-border rounded-lg p-5 space-y-4" aria-labelledby="reputation-credibility-heading">
        <div className="flex items-start gap-3">
          <ShieldCheck className="w-5 h-5 text-cyan-400 mt-0.5" aria-hidden="true" />
          <div>
            <h3 id="reputation-credibility-heading" className="text-sm font-semibold text-slate-100">Review credibility & evidence coverage</h3>
            <p className="text-xs text-slate-400 mt-1">
              Credibility labels reflect available review evidence. Dataset totals are indexed records and are not a claim that each record has been independently verified.
            </p>
          </div>
        </div>

        <div className="bg-shield-surface border border-shield-border rounded p-3 w-fit min-w-40">
          <span className="block text-[10px] text-slate-400 uppercase">Reputation confidence</span>
          <span className="text-xl font-semibold text-cyan-300">{formatPercent(confidence)}</span>
        </div>

        {hasCredibilitySummary ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
            <div className="bg-shield-surface border border-shield-border rounded p-3">
              <span className="block text-[10px] text-slate-400 uppercase">Credibility score</span>
              <span className="text-xl font-semibold text-cyan-300">{formatScore(credibilityScore)}</span>
            </div>
            <div className="bg-shield-surface border border-shield-border rounded p-3">
              <span className="block text-[10px] text-slate-400 uppercase">Evidence coverage</span>
              <span className="text-xl font-semibold text-slate-100">{formatPercent(evidenceCoverage)}</span>
            </div>
            <CountCard label="Credible reviews" value={credible} color="text-emerald-300" />
            <CountCard label="Needs verification" value={needsVerification} color="text-amber-300" />
            <CountCard label="Suspicious reviews" value={suspicious} color="text-rose-300" />
          </div>
        ) : (
          <p className="text-xs text-slate-400 bg-shield-surface border border-shield-border rounded p-3">
            Review-level credibility counts and evidence coverage are not provided by this response.
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {evidenceItems.length > 0 && (
              <div className="bg-shield-surface border border-shield-border rounded p-3">
                <h4 className="text-xs font-semibold text-slate-200 mb-2">Evidence considered</h4>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {evidenceItems.map((item, index) => <li key={index}>{evidenceText(item)}</li>)}
                </ul>
              </div>
            )}
            {evidenceItems.length === 0 && (
              <div className="bg-shield-surface border border-shield-border rounded p-3">
                <h4 className="text-xs font-semibold text-slate-200 mb-2">Evidence considered</h4>
                <p className="text-xs text-slate-400">No evidence details were included in this response.</p>
              </div>
            )}
            {limitationItems.length > 0 ? (
              <div className="bg-shield-surface border border-amber-500/20 rounded p-3">
                <h4 className="text-xs font-semibold text-amber-200 mb-2">Limitations</h4>
                <ul className="space-y-1.5 text-xs text-slate-300">
                  {limitationItems.map((item, index) => <li key={index}>{evidenceText(item)}</li>)}
                </ul>
              </div>
            ) : (
              <div className="bg-shield-surface border border-shield-border rounded p-3">
                <h4 className="text-xs font-semibold text-slate-200 mb-2">Limitations</h4>
                <p className="text-xs text-slate-400">No limitations details were included in this response.</p>
              </div>
            )}
        </div>
      </section>

      {!hasLegacyReviewData ? (
        <div className="bg-shield-card border border-shield-border rounded-lg p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5" aria-hidden="true" />
            <div>
              <h4 className="text-sm font-semibold text-slate-200">
                {datasetAvailable === false ? 'Review dataset unavailable' : 'Insufficient indexed review evidence'}
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                {datasetAvailable === false
                  ? 'The review dataset could not be accessed for this request. Reputation ratings and workplace aspects cannot be summarized.'
                  : `No matching employee review records are currently indexed for “${companyName}”. Reputation ratings and workplace aspects cannot be summarized from the available records.`}
              </p>
            </div>
          </div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-shield-card border border-shield-border rounded-lg p-4">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Indexed review records</div>
              <div className="text-2xl font-bold font-mono text-slate-100">{reviewCount}</div>
              <div className="text-[11px] text-slate-400 mt-1">Dataset records; not individually verified</div>
            </div>

            <div className="bg-shield-card border border-shield-border rounded-lg p-4">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Average rating</div>
              <div className="flex items-center gap-2">
                <span className="text-2xl font-bold font-mono text-amber-400">{typeof averageRating === 'number' ? averageRating.toFixed(1) : 'N/A'}</span>
                <div className="flex text-amber-400" aria-label={typeof averageRating === 'number' ? `${averageRating.toFixed(1)} out of 5 stars` : 'Rating unavailable'}>
                  {[...Array(5)].map((_, index) => (
                    <Star key={index} className={`w-3.5 h-3.5 ${index < Math.round(averageRating || 0) ? 'fill-amber-400' : 'text-slate-600'}`} aria-hidden="true" />
                  ))}
                </div>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">Out of 5.0 stars</div>
            </div>

            <div className="bg-shield-card border border-shield-border rounded-lg p-4">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Reputation confidence</div>
              <div className="text-2xl font-bold font-mono text-cyan-400">{formatPercent(confidence)}</div>
              <div className="text-[11px] text-slate-400 mt-1">Based on available sample information</div>
            </div>

            <div className="bg-shield-card border border-shield-border rounded-lg p-4">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">Sentiment split</div>
              <div className="flex flex-wrap items-center gap-x-3 text-xs font-mono mt-1">
                <span className="text-emerald-400 font-semibold">{sentimentDistribution.positive || 0} Pos</span>
                <span className="text-slate-400 font-semibold">{sentimentDistribution.neutral || 0} Neu</span>
                <span className="text-rose-400 font-semibold">{sentimentDistribution.negative || 0} Neg</span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1.5">Based on indexed review sentiment</div>
            </div>
          </div>

          <div className="bg-shield-card border border-shield-border rounded-lg p-5">
            <h4 className="text-sm font-semibold text-slate-200 mb-3">Sentiment distribution</h4>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sentimentData} margin={{ top: 10, right: 20, left: -20, bottom: 5 }}>
                  <XAxis dataKey="name" stroke="#64748B" fontSize={11} tickLine={false} />
                  <YAxis stroke="#64748B" fontSize={11} tickLine={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#111827', borderColor: '#1E293B', fontSize: '12px' }}
                    cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
                  />
                  <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                    {sentimentData.map((entry, index) => <Cell key={`cell-${index}`} fill={entry.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {Object.keys(aspects).length > 0 && (
            <div className="bg-shield-card border border-shield-border rounded-lg p-5">
              <div className="mb-4">
                <h4 className="text-sm font-semibold text-slate-200">Workplace aspect assessment</h4>
                <p className="text-xs text-slate-400 mt-0.5">Aspect scores and summaries based on the available employee review records.</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(aspects).map(([aspectKey, aspectValue]) => {
                  const Icon = ASPECT_ICONS[aspectKey] || Clock;
                  const badge = getAspectBadge(aspectValue?.status);
                  return (
                    <div key={aspectKey} className="bg-shield-surface border border-shield-border p-3.5 rounded-lg flex flex-col justify-between">
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 text-cyan-400" aria-hidden="true" />
                          <span className="text-xs font-semibold text-slate-200">{ASPECT_LABELS[aspectKey] || aspectKey}</span>
                        </div>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-medium border ${badge.bg}`}>{badge.label}</span>
                      </div>
                      <p className="text-[11px] text-slate-300 leading-relaxed mb-2">
                        {aspectValue?.evidence || 'No specific feedback recorded for this aspect.'}
                      </p>
                      <div className="text-[10px] text-slate-400 flex items-center justify-between font-mono pt-2 border-t border-shield-border/40">
                        <span>Score: {typeof aspectValue?.score === 'number' ? aspectValue.score.toFixed(1) : 'N/A'}/5.0</span>
                        <span>Mentions: {aspectValue?.mention_count ?? 'N/A'}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
