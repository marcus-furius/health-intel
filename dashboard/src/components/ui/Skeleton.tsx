interface Props {
  className?: string;
}

export default function Skeleton({ className = 'h-4 w-24' }: Props) {
  return (
    <div className={`animate-warm-pulse rounded-lg bg-bg-elevated ${className}`} />
  );
}
