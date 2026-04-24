import { colors } from '../../lib/colors.ts';

interface Props {
  score: number;
  size?: number;
  label?: string;
  showScore?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 80) return colors.sage;
  if (score >= 60) return colors.gold;
  if (score >= 40) return colors.terracotta;
  return colors.rose;
}

export default function GaugeChart({ score, size = 160, label, showScore = true }: Props) {
  const radius = (size - 16) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, Math.min(100, score)) / 100;
  const dashOffset = circumference * (1 - progress);
  const color = scoreColor(score);

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={8}
          className="text-border-subtle"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={8}
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      {showScore && (
        <div
          className="absolute flex flex-col items-center justify-center"
          style={{ width: size, height: size }}
        >
          <span className="font-serif text-text-primary" style={{ fontSize: size * 0.22 }}>
            {Math.round(score)}
          </span>
          {label && (
            <span className="text-text-muted" style={{ fontSize: Math.max(10, size * 0.08) }}>
              {label}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
