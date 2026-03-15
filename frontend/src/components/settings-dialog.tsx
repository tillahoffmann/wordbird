import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { toast } from "sonner"
import { fetchConfig, saveConfig, type ConfigData } from "@/lib/api"

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [config, setConfig] = useState<ConfigData | null>(null)
  const [modifierKeyOptions, setModifierKeyOptions] = useState<string[]>([])
  const [toggleKeyOptions, setToggleKeyOptions] = useState<string[]>([])
  const [keyLabels, setKeyLabels] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      fetchConfig().then((data) => {
        setConfig(data.config)
        setModifierKeyOptions(data.modifier_key_options)
        setToggleKeyOptions(data.toggle_key_options)
        setKeyLabels(data.key_labels)
      })
    }
  }, [open])

  async function handleSave() {
    if (!config) return
    setSaving(true)
    const ok = await saveConfig(config)
    setSaving(false)
    if (ok) {
      toast("Settings saved")
      onOpenChange(false)
    } else {
      toast.error("Failed to save settings")
    }
  }

  if (!config) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Settings</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="modifier_key">Modifier key</Label>
            <Select
              value={config.modifier_key}
              onValueChange={(v) => v && setConfig({ ...config, modifier_key: v })}
            >
              <SelectTrigger id="modifier_key">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {modifierKeyOptions.map((k) => (
                  <SelectItem key={k} value={k}>
                    {keyLabels[k] || k} ({k})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="toggle_key">Toggle key</Label>
            <Select
              value={config.toggle_key}
              onValueChange={(v) => v && setConfig({ ...config, toggle_key: v })}
            >
              <SelectTrigger id="toggle_key">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {toggleKeyOptions.map((k) => (
                  <SelectItem key={k} value={k}>
                    {keyLabels[k] || k} ({k})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="transcription_model">Transcription model</Label>
            <Input
              id="transcription_model"
              value={config.transcription_model}
              onChange={(e) =>
                setConfig({ ...config, transcription_model: e.target.value })
              }
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="fix_model">Post-processing model</Label>
            <Input
              id="fix_model"
              value={config.fix_model}
              onChange={(e) =>
                setConfig({ ...config, fix_model: e.target.value })
              }
            />
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="no_fix"
              checked={config.no_fix}
              onCheckedChange={(checked) =>
                setConfig({ ...config, no_fix: checked === true })
              }
            />
            <Label htmlFor="no_fix">Disable post-processing</Label>
          </div>
        </div>
        <DialogFooter>
          <Button onClick={handleSave} disabled={saving} className="w-full">
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
