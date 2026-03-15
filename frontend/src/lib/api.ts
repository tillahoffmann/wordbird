export interface Transcription {
  id: number
  timestamp: string
  raw_text: string
  fixed_text: string | null
  app_name: string | null
  duration_seconds: number | null
  cwd: string | null
}

export interface Stats {
  total_words: number
  total_seconds: number
  total_transcriptions: number
}

export interface ConfigData {
  modifier_key: string
  toggle_key: string
  transcription_model: string
  fix_model: string
  no_fix: boolean
}

export interface ConfigResponse {
  config: ConfigData
  modifier_key_options: string[]
  toggle_key_options: string[]
  key_labels: Record<string, string>
  transcription_model_suggestions: string[]
  fix_model_suggestions: string[]
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch("/api/stats")
  return res.json()
}

export async function fetchTranscriptions(limit = 50): Promise<Transcription[]> {
  const res = await fetch(`/api/transcriptions?limit=${limit}`)
  const data = await res.json()
  return data.transcriptions
}

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch("/api/config")
  return res.json()
}

export async function saveConfig(update: Partial<ConfigData>): Promise<boolean> {
  const res = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  })
  const data = await res.json()
  return data.ok === true
}
