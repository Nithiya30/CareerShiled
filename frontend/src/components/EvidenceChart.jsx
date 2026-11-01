import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell
} from 'recharts';

export default function EvidenceChart({ contributions = [] }) {
  // contributions: [{ category: 'Job ML', contribution: 0.25, state: 'positive' }, ...]
  const chartData = contributions.length > 0 ? contributions : [
    { category: 'Job ML', contribution: 0 },
    { category: 'Scam', contribution: 0 },
    { category: 'Recruiter', contribution: 0 },
    { category: 'Company', contribution: 0 },
    { category: 'Website', contribution: 0 },
    { category: 'Domain', contribution: 0 },
    { category: 'Salary', contribution: 0 },
    { category: 'Transformer', contribution: 0 },
  ];

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const val = data.contribution;
      const isPositive = val > 0;
      const isNegative = val < 0;

      return (
        <div className="bg-shield-surface border border-shield-border p-3 rounded-md shadow-lg text-xs">
          <div className="font-semibold text-slate-200 mb-1">{data.category}</div>
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Contribution:</span>
            <span className={`font-mono font-bold ${isPositive ? 'text-emerald-400' : isNegative ? 'text-rose-400' : 'text-slate-300'}`}>
              {isPositive ? `+${val.toFixed(3)}` : val.toFixed(3)}
            </span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">
            {isPositive ? 'Increased trust (legitimate signal)' : isNegative ? 'Decreased trust (risk signal)' : 'Neutral / unknown influence'}
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <div className="bg-shield-card border border-shield-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100">Evidence Contribution</h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Normalized impact of each evidence source on the final recruitment trust score
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs font-mono">
          <span className="flex items-center gap-1.5 text-emerald-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block" /> Positive
          </span>
          <span className="flex items-center gap-1.5 text-rose-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-rose-500 inline-block" /> Negative
          </span>
          <span className="flex items-center gap-1.5 text-slate-400">
            <span className="w-2.5 h-2.5 rounded-sm bg-slate-600 inline-block" /> Neutral/Unknown
          </span>
        </div>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            margin={{ top: 15, right: 20, left: -10, bottom: 25 }}
          >
            <XAxis
              dataKey="category"
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              angle={-20}
              textAnchor="end"
              interval={0}
            />
            <YAxis
              stroke="#64748B"
              fontSize={11}
              tickLine={false}
              domain={[-1, 1]}
              tickFormatter={(v) => v.toFixed(1)}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="#334155" strokeDasharray="3 3" />
            <Bar dataKey="contribution" radius={[3, 3, 0, 0]}>
              {chartData.map((entry, index) => {
                const val = entry.contribution;
                let fillColor = '#64748B'; // Neutral
                if (val > 0.01) fillColor = '#10B981'; // Positive
                else if (val < -0.01) fillColor = '#EF4444'; // Negative
                return <Cell key={`cell-${index}`} fill={fillColor} />;
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
