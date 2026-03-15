import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import type { Transcription } from "@/lib/api"
import { toast } from "sonner"

interface TranscriptListProps {
  transcriptions: Transcription[]
}

function shortenPath(cwd: string): string {
  const parts = cwd.split("/")
  if (parts.length >= 3 && parts[1] === "Users") {
    return "~/" + parts.slice(3).join("/")
  }
  return cwd
}

function TranscriptItem({ t }: { t: Transcription }) {
  const [showOriginal, setShowOriginal] = useState(false)
  const displayText = t.fixed_text || t.raw_text
  const hasOriginal = t.fixed_text && t.fixed_text !== t.raw_text

  function copyText() {
    navigator.clipboard.writeText(displayText).then(
      () => toast("Copied to clipboard"),
      () => toast.error("Failed to copy")
    )
  }

  return (
    <div className="p-4 rounded-lg bg-card">
      <div className="flex justify-between items-start">
        <div className="flex gap-2 text-xs text-muted-foreground flex-wrap items-center mb-1">
          <span>{t.timestamp.slice(0, 16).replace("T", " ")}</span>
          {t.app_name && <Badge variant="secondary">{t.app_name}</Badge>}
          {t.duration_seconds != null && (
            <span className="tabular-nums">{t.duration_seconds.toFixed(1)}s</span>
          )}
          {t.cwd && (
            <span>
              <code className="text-xs">{shortenPath(t.cwd)}</code>
            </span>
          )}
        </div>
        <button
          onClick={copyText}
          className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
          title="Copy to clipboard"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" strokeWidth="2" />
            <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" strokeWidth="2" />
          </svg>
        </button>
      </div>
      <div className="break-words">{displayText}</div>
      {hasOriginal && (
        <div className="mt-1">
          <button
            onClick={() => setShowOriginal(!showOriginal)}
            className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
          >
            {showOriginal ? "Hide" : "Show"} original
          </button>
          {showOriginal && (
            <div className="text-sm text-muted-foreground mt-1">{t.raw_text}</div>
          )}
        </div>
      )}
    </div>
  )
}

export function TranscriptList({ transcriptions }: TranscriptListProps) {
  if (transcriptions.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <div className="text-4xl mb-4">🎙️</div>
        <p>No transcriptions yet.</p>
        <p className="text-sm">Press your hotkey to start dictating.</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {transcriptions.map((t) => (
        <TranscriptItem key={t.id} t={t} />
      ))}
    </div>
  )
}
