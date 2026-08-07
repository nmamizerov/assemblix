import { useMemo, useRef, useState } from "react";
import { ChevronDown } from "lucide-react";

import { Input } from "@/shared/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/shared/ui/popover";

interface VoiceOption {
  id: string;
  name: string;
}

interface VoiceComboboxProps {
  value: string;
  options: VoiceOption[];
  disabled?: boolean;
  placeholder?: string;
  onChange: (value: string) => void;
}

/**
 * A voice picker you can also type into. OpenAI accepts a custom voice id
 * (`voice_…`, created through /v1/audio/voices) anywhere a built-in voice name
 * goes, and those ids belong to the customer's own account — we cannot list them,
 * so the field has to accept text a catalog will never contain.
 */
export const VoiceCombobox = ({
  value,
  options,
  disabled,
  placeholder,
  onChange,
}: VoiceComboboxProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => {
    const query = value.trim().toLowerCase();
    if (!query) return options;
    return options.filter(
      (option) =>
        option.name.toLowerCase().includes(query) ||
        option.id.toLowerCase().includes(query)
    );
  }, [options, value]);

  const handleSelect = (optionId: string) => {
    onChange(optionId);
    setIsOpen(false);
    inputRef.current?.focus();
  };

  return (
    <Popover open={isOpen && matches.length > 0} onOpenChange={setIsOpen}>
      <PopoverAnchor asChild>
        <div className="relative">
          <Input
            ref={inputRef}
            value={value}
            disabled={disabled}
            placeholder={placeholder}
            spellCheck={false}
            className="pr-9"
            onChange={(event) => {
              onChange(event.target.value);
              setIsOpen(true);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={(event) => {
              if (event.key === "Escape") setIsOpen(false);
            }}
          />
          <button
            type="button"
            tabIndex={-1}
            disabled={disabled}
            aria-label={placeholder}
            onClick={() => setIsOpen((open) => !open)}
            className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground disabled:opacity-50"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </div>
      </PopoverAnchor>

      <PopoverContent
        align="start"
        className="w-(--radix-popover-trigger-width) p-1"
        // Keep the caret in the field while the list is open.
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        <ul className="max-h-60 overflow-y-auto">
          {matches.map((option) => (
            <li key={option.id}>
              <button
                type="button"
                onClick={() => handleSelect(option.id)}
                className="w-full rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent"
              >
                {option.name}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
};
