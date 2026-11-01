import React from 'react';

export default function TrustScore({ score = 50, size = 160, strokeWidth = 12, showLabel = true }) {
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

  let color = '#F59E0B'; // Needs Verification (amber)
  let statusText = 'Needs Verification';
  let textColor = 'text-amber-400';
  let glowColor = 'rgba(245, 158, 11, 0.2)';

  if (clampedScore >= 75) {
    color = '#10B981'; // Legitimate (green)
    statusText = 'Likely Legitimate';
    textColor = 'text-emerald-400';
    glowColor = 'rgba(16, 185, 129, 0.2)';
  } else if (clampedScore < 50) {
    color = '#EF4444'; // Fraudulent (red)
    statusText = 'Likely Fraudulent';
    textColor = 'text-rose-400';
    glowColor = 'rgba(239, 68, 68, 0.2)';
  }

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = (clampedScore / 100) * circumference;
  const strokeDashoffset = circumference - progress;

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          {/* Background track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke="#1E293B"
            strokeWidth={strokeWidth}
            fill="transparent"
          />
          {/* Progress circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            fill="transparent"
            style={{
              transition: 'stroke-dashoffset 0.8s ease-in-out',
              filter: `drop-shadow(0 0 6px ${glowColor})`
            }}
          />
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <div className="text-3xl font-bold font-mono tracking-tight text-slate-100">
            {clampedScore}
          </div>
          <div className="text-xs text-slate-400 font-mono">/ 100</div>
        </div>
      </div>

      {showLabel && (
        <div className="mt-3 text-center">
          <span className={`text-sm font-semibold tracking-wide ${textColor}`}>
            {statusText}
          </span>
          <div className="text-xs text-slate-400 mt-0.5">Recruitment Trust Score</div>
        </div>
      )}
    </div>
  );
}
