import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
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
import { ComboboxInput } from "@/components/combobox-input"

interface SettingsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [config, setConfig] = useState<ConfigData | null>(null)
  const [modifierKeyOptions, setModifierKeyOptions] = useState<string[]>([])
  const [toggleKeyOptions, setToggleKeyOptions] = useState<string[]>([])
  const [keyLabels, setKeyLabels] = useState<Record<string, string>>({})
  const [sttModels, setSttModels] = useState<string[]>([])
  const [fixModels, setFixModels] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (open) {
      fetchConfig().then((data) => {
        setConfig(data.config)
        setModifierKeyOptions(data.modifier_key_options)
        setToggleKeyOptions(data.toggle_key_options)
        setKeyLabels(data.key_labels)
        setSttModels(data.transcription_model_suggestions)
        setFixModels(data.fix_model_suggestions)
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
                <SelectValue>
                  {keyLabels[config.modifier_key] || config.modifier_key}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {modifierKeyOptions.map((k) => (
                  <SelectItem key={k} value={k}>
                    {keyLabels[k] || k}
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
                <SelectValue>
                  {keyLabels[config.toggle_key] || config.toggle_key}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {toggleKeyOptions.map((k) => (
                  <SelectItem key={k} value={k}>
                    {keyLabels[k] || k}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="transcription_model">Transcription model</Label>
            <ComboboxInput
              id="transcription_model"
              value={config.transcription_model}
              onChange={(v) => setConfig({ ...config, transcription_model: v })}
              suggestions={sttModels}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="fix_model">Post-processing model</Label>
            <ComboboxInput
              id="fix_model"
              value={config.fix_model}
              onChange={(v) => setConfig({ ...config, fix_model: v })}
              suggestions={fixModels}
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

          <div className="flex items-center gap-2">
            <Checkbox
              id="sound"
              checked={config.sound}
              onCheckedChange={(checked) =>
                setConfig({ ...config, sound: checked === true })
              }
            />
            <Label htmlFor="sound">Play sound when mic is ready</Label>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="submit_with_return"
              checked={config.submit_with_return}
              onCheckedChange={(checked) =>
                setConfig({ ...config, submit_with_return: checked === true })
              }
            />
            <Label htmlFor="submit_with_return">
              YOLO mode (submit with{" "}
              <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-mono">
                {keyLabels[config.modifier_key] || config.modifier_key}
              </kbd>
              {" + "}
              <kbd className="rounded border bg-muted px-1.5 py-0.5 text-xs font-mono">
                Return
              </kbd>
              )
            </Label>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="save_audio"
              checked={config.save_audio}
              onCheckedChange={(checked) =>
                setConfig({ ...config, save_audio: checked === true })
              }
            />
            <Label htmlFor="save_audio">Save audio recordings</Label>
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
