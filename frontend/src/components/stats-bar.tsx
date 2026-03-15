import type { Stats } from "@/lib/api"

interface StatsBarProps {
  stats: Stats | null
}

function formatDuration(seconds: number): string {
  let s = Math.floor(seconds)
  if (s < 60) return `${s}s`
  let m = Math.floor(s / 60)
  s = s % 60
  if (m < 60) return `${m}m ${s}s`
  let h = Math.floor(m / 60)
  m = m % 60
  if (h < 24) return `${h}h ${m}m`
  const d = Math.floor(h / 24)
  h = h % 24
  return `${d}d ${h}h`
}

function formatNumber(n: number): string {
  return n.toLocaleString()
}

function StatItem({ value, label }: { value: string | number; label: string }) {
  return (
    <div className="text-center">
      <div className="text-2xl font-bold text-primary">{value}</div>
      <div className="text-xs text-muted-foreground uppercase">{label}</div>
    </div>
  )
}

export function StatsBar({ stats }: StatsBarProps) {
  if (!stats) return null

  const totalMins = stats.total_seconds / 60
  const wpm = totalMins > 0 ? Math.round(stats.total_words / totalMins) : 0

  return (
    <div className="flex gap-8 mb-6">
      <StatItem value={formatNumber(stats.total_words)} label="Words" />
      <StatItem value={formatDuration(stats.total_seconds)} label="Recording" />
      <StatItem value={formatNumber(wpm)} label="WPM" />
      <StatItem value={formatNumber(stats.total_transcriptions)} label="Sessions" />
    </div>
  )
}
