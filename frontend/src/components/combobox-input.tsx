import { useState, useRef, useEffect } from "react"
import { Input } from "@/components/ui/input"

interface ComboboxInputProps {
  id?: string
  value: string
  onChange: (value: string) => void
  suggestions: string[]
  placeholder?: string
}

export function ComboboxInput({
  id,
  value,
  onChange,
  suggestions,
  placeholder,
}: ComboboxInputProps) {
  const [open, setOpen] = useState(false)
  const [filter, setFilter] = useState("")
  const ref = useRef<HTMLDivElement>(null)

  // Close on click outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handleClick)
    return () => document.removeEventListener("mousedown", handleClick)
  }, [])

  const filtered = suggestions.filter((s) =>
    s.toLowerCase().includes((filter || value).toLowerCase())
  )

  return (
    <div ref={ref} className="relative">
      <Input
        id={id}
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value)
          setFilter(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
      />
      {open && filtered.length > 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover p-1 shadow-md">
          {filtered.map((s) => (
            <button
              key={s}
              className={`w-full rounded px-2 py-1.5 text-left text-sm hover:bg-accent ${
                s === value ? "bg-accent" : ""
              }`}
              onMouseDown={(e) => {
                e.preventDefault()
                onChange(s)
                setFilter("")
                setOpen(false)
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
