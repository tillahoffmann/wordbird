import { useEffect, useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { StatsBar } from "@/components/stats-bar"
import { TranscriptList } from "@/components/transcript-list"
import { SettingsDialog } from "@/components/settings-dialog"
import { fetchStats, fetchTranscriptions, type Stats, type Transcription } from "@/lib/api"

function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([])
  const [settingsOpen, setSettingsOpen] = useState(
    window.location.hash === "#settings"
  )

  function refresh() {
    fetchStats().then(setStats)
    fetchTranscriptions().then(setTranscriptions)
  }

  function setSettingsOpenWithHash(open: boolean) {
    setSettingsOpen(open)
    window.location.hash = open ? "#settings" : ""
  }

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 5000)
    const onFocus = () => refresh()
    const onHashChange = () => {
      setSettingsOpen(window.location.hash === "#settings")
    }
    const darkQuery = window.matchMedia("(prefers-color-scheme: dark)")
    const onDarkChange = (e: MediaQueryListEvent) => {
      document.documentElement.classList.toggle("dark", e.matches)
    }
    darkQuery.addEventListener("change", onDarkChange)
    window.addEventListener("focus", onFocus)
    window.addEventListener("hashchange", onHashChange)
    return () => {
      clearInterval(interval)
      window.removeEventListener("focus", onFocus)
      window.removeEventListener("hashchange", onHashChange)
      darkQuery.removeEventListener("change", onDarkChange)
    }
  }, [])

  return (
    <div className="flex flex-col h-screen max-w-3xl mx-auto px-4">
      <header className="flex justify-between items-center py-4 shrink-0">
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <img src="/icon.svg" alt="" className="w-7 h-7 dark:invert" />
          Wordbird
        </h1>
        <button
          onClick={() => setSettingsOpenWithHash(true)}
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

      <div className="flex-1 overflow-y-auto min-h-0 pb-4">
        <TranscriptList transcriptions={transcriptions} onDelete={refresh} />
      </div>

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpenWithHash} />
      <Toaster />
    </div>
  )
}

export default App
