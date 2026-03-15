import { useEffect, useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { StatsBar } from "@/components/stats-bar"
import { TranscriptList } from "@/components/transcript-list"
import { SettingsDialog } from "@/components/settings-dialog"
import { fetchStats, fetchTranscriptions, type Stats, type Transcription } from "@/lib/api"

function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)

  function refresh() {
    fetchStats().then(setStats)
    fetchTranscriptions().then(setTranscriptions)
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="max-w-3xl mx-auto px-4 py-4 min-h-screen">
      <header className="flex justify-between items-center mb-4">
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <img src="/icon.svg" alt="" className="w-7 h-7 dark:invert" />
          Wordbird
        </h1>
        <button
          onClick={() => setSettingsOpen(true)}
          className="text-muted-foreground hover:text-foreground p-2 rounded-lg transition-colors"
          title="Settings"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"
            />
          </svg>
        </button>
      </header>

      <StatsBar stats={stats} />
      <TranscriptList transcriptions={transcriptions} />
      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      <Toaster />
    </div>
  )
}

export default App
