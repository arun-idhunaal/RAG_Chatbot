import { useEffect, useRef, useState } from "react";

type Props = {
  disabled?: boolean;
  onSend: (text: string) => void;
};

export function Composer({ disabled, onSend }: Props) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  const canSend = value.trim().length > 0 && !disabled;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  }, [value]);

  function submit() {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue("");
  }

  return (
    <div className="relative flex items-end gap-2 bg-[#171A22] border border-outline-variant rounded-2xl p-2 shadow-[0_8px_32px_rgba(0,0,0,0.4)] focus-within:border-primary/50">
      <textarea
        ref={ref}
        rows={1}
        disabled={disabled}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Ask a facts-only mutual fund question…"
        className="w-full bg-transparent border-none text-on-surface text-sm placeholder:text-outline focus:ring-0 resize-none py-2 px-2 max-h-[120px] custom-scrollbar outline-none"
      />
      <button
        type="button"
        disabled={!canSend}
        onClick={submit}
        className={`p-2 rounded-full flex-shrink-0 transition-colors ${
          canSend
            ? "bg-primary-container text-on-primary-container"
            : "bg-surface-container-high text-outline"
        }`}
        aria-label="Send"
      >
        <span className="material-symbols-outlined text-[20px]">send</span>
      </button>
    </div>
  );
}
