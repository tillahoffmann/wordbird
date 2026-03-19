import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { deleteTranscription, type Transcription } from "@/lib/api"
import { toast } from "sonner"

interface TranscriptListProps {
  transcriptions: Transcription[]
  onDelete?: () => void
}

function shortenPath(cwd: string): string {
  const parts = cwd.split("/")
  if (parts.length >= 3 && parts[1] === "Users") {
    return "~/" + parts.slice(3).join("/")
  }
  return cwd
}

function formatDuration(seconds: number): string {
  if (seconds < 1) return "<1s"
  const s = Math.floor(seconds)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`
}

function TranscriptItem({ t, onDelete }: { t: Transcription; onDelete?: () => void }) {
  const [showOriginal, setShowOriginal] = useState(false)
  const displayText = t.fixed_text || t.raw_text
  const wasChanged = t.fixed_text != null && t.fixed_text !== t.raw_text
  const wasPostProcessed = t.fixed_text != null

  function copyText() {
    navigator.clipboard.writeText(displayText).then(
      () => toast("Copied to clipboard"),
      () => toast.error("Failed to copy")
    )
  }

  function handleDelete() {
    deleteTranscription(t.id).then((ok) => {
      if (ok) {
        toast("Deleted")
        onDelete?.()
      } else {
        toast.error("Failed to delete")
      }
    })
  }

  return (
    <div className="p-4 rounded-lg bg-card">
      <div className="flex justify-between items-start">
        <div className="flex gap-2 text-xs text-muted-foreground flex-wrap items-center mb-1">
          <span>{t.timestamp.slice(0, 16).replace("T", " ")}</span>
          {t.app_name && <Badge variant="secondary">{t.app_name}</Badge>}
          {t.duration_seconds != null && (
            <span className="tabular-nums">{formatDuration(t.duration_seconds)}</span>
          )}
          {t.cwd && (
            <span>
              <code className="text-xs">{shortenPath(t.cwd)}</code>
            </span>
          )}
        </div>
        <div className="flex gap-1">
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
          <button
            onClick={handleDelete}
            className="text-muted-foreground hover:text-destructive p-1 rounded transition-colors"
            title="Delete"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2" strokeLinecap="round">
              <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6" />
            </svg>
          </button>
        </div>
      </div>
      <div className="break-words">{displayText}</div>
      <div className="mt-1">
        {wasChanged ? (
          <>
            <button
              onClick={() => setShowOriginal(!showOriginal)}
              className="text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
              {showOriginal ? "Hide" : "Show"} original
            </button>
            {showOriginal && (
              <div className="text-sm text-muted-foreground mt-1">{t.raw_text}</div>
            )}
          </>
        ) : wasPostProcessed ? (
          <span className="text-xs text-muted-foreground/50 italic">No corrections needed</span>
        ) : (
          <span className="text-xs text-muted-foreground/50 italic">Not post-processed</span>
        )}
      </div>
      {t.audio_filename && (
        <audio
          controls
          preload="none"
          className="mt-2 h-8 w-full"
          src={`/audio/${t.audio_filename}`}
        />
      )}
    </div>
  )
}

export function TranscriptList({ transcriptions, onDelete }: TranscriptListProps) {
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
        <TranscriptItem key={t.id} t={t} onDelete={onDelete} />
      ))}
    </div>
  )
}
