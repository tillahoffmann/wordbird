import { useEffect, useMemo, useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { StatsBar } from "@/components/stats-bar"
import { TranscriptList } from "@/components/transcript-list"
import { SettingsDialog } from "@/components/settings-dialog"
import { fetchStats, fetchTranscriptions, type Stats, type Transcription } from "@/lib/api"

const PAGE_SIZE = 30

function App() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([])
  const [settingsOpen, setSettingsOpen] = useState(
    window.location.hash === "#settings"
  )
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => {
    if (!search.trim()) return transcriptions
    const q = search.toLowerCase()
    return transcriptions.filter(
      (t) =>
        t.raw_text.toLowerCase().includes(q) ||
        (t.fixed_text && t.fixed_text.toLowerCase().includes(q)) ||
        (t.app_name && t.app_name.toLowerCase().includes(q))
    )
  }, [transcriptions, search])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, totalPages - 1)
  const paged = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE)

  function refresh() {
    fetchStats().then(setStats)
    fetchTranscriptions(1000).then(setTranscriptions)
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

      {transcriptions.length > 0 && (
        <div className="shrink-0 mb-3">
          <Input
            placeholder="Search transcriptions..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0) }}
          />
        </div>
      )}

      <div className="flex-1 overflow-y-auto min-h-0 pb-4">
        <TranscriptList transcriptions={paged} onDelete={refresh} />
      </div>

      {totalPages > 1 && (
        <div className="shrink-0 flex items-center justify-center gap-2 py-3 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(safePage - 1)}
            disabled={safePage === 0}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground tabular-nums">
            {safePage + 1} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(safePage + 1)}
            disabled={safePage >= totalPages - 1}
          >
            Next
          </Button>
        </div>
      )}

      <SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpenWithHash} />
      <Toaster />
    </div>
  )
}

export default App
