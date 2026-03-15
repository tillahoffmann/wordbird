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
  const [dark, setDark] = useState(
    document.documentElement.classList.contains("dark")
  )

  function toggleDark() {
    const next = !dark
    setDark(next)
    document.documentElement.classList.toggle("dark", next)
  }

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
        <div className="flex items-center gap-1">
        <a
          href="https://github.com/tillahoffmann/wordbird"
          target="_blank"
          rel="noopener noreferrer"
          className="text-muted-foreground hover:text-foreground p-2 rounded-lg transition-colors"
          title="GitHub"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
        </a>
        <button
          onClick={toggleDark}
          className="text-muted-foreground hover:text-foreground p-2 rounded-lg transition-colors"
          title={dark ? "Light mode" : "Dark mode"}
        >
          {dark ? (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} strokeLinecap="round">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2} strokeLinecap="round">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
          )}
        </button>
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
        </div>
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
