import type { SchemeInfo } from "./types";

const ICONS: Record<string, string> = {
  icici_nasdaq100_dg: "show_chart",
  icici_midcap_dg: "trending_up",
  icici_flexicap_dg: "pie_chart",
  icici_largecap_dg: "account_balance",
  icici_elss_dg: "savings",
};

function shortName(canonical: string): string {
  return canonical
    .replace("ICICI Prudential ", "")
    .replace(" (Direct Growth)", "")
    .replace(" (Direct Plan Growth)", "");
}

type Props = {
  schemes: SchemeInfo[];
  disclaimer: string;
  open: boolean;
  onClose: () => void;
  onClear: () => void;
  onAskScheme: (canonicalName: string) => void;
};

export function Sidebar({
  schemes,
  disclaimer,
  open,
  onClose,
  onClear,
  onAskScheme,
}: Props) {
  return (
    <>
      {open ? (
        <button
          type="button"
          className="md:hidden fixed inset-0 bg-black/50 z-40"
          aria-label="Close menu"
          onClick={onClose}
        />
      ) : null}
      <aside
        className={`flex flex-col fixed left-0 top-0 h-full w-[300px] p-4 gap-3 bg-surface-container-low border-r border-outline-variant z-50 transition-transform md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full md:translate-x-0"
        }`}
      >
        <div className="flex items-center gap-3 mb-4 px-2 pt-2">
          <div className="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary-container font-semibold">
            I
          </div>
          <div>
            <h1 className="text-lg font-semibold text-on-surface leading-6">
              INDmoney MF FAQ
            </h1>
            <p className="text-xs font-medium text-on-surface-variant">
              ICICI Prudential · 5 schemes
            </p>
          </div>
        </div>
        <p className="font-semibold text-[10px] tracking-[0.04em] text-outline px-3 uppercase">
          Supported schemes
        </p>
        <nav className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1 px-1">
          {schemes.map((s) => (
            <button
              key={s.scheme_id}
              type="button"
              title={s.canonical_name}
              onClick={() => {
                onAskScheme(s.canonical_name);
                onClose();
              }}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-surface-container-high text-left text-on-surface-variant text-xs font-medium group"
            >
              <span className="material-symbols-outlined text-[18px] group-hover:text-primary-container">
                {ICONS[s.scheme_id] ?? "description"}
              </span>
              <span className="leading-snug">{shortName(s.canonical_name)}</span>
            </button>
          ))}
        </nav>
        <div className="mt-auto flex flex-col gap-3 px-2 pb-2">
          <button
            type="button"
            onClick={onClear}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-outline-variant text-on-surface-variant hover:bg-surface-container hover:text-on-surface text-xs font-medium"
          >
            <span className="material-symbols-outlined text-[16px]">delete_sweep</span>
            Clear chat
          </button>
          <div className="flex items-center gap-2 px-3 py-2 bg-surface-container-lowest rounded-md border border-white/10">
            <span className="material-symbols-outlined text-outline text-[14px]">lock</span>
            <span className="text-[11px] font-semibold text-outline leading-4">
              {disclaimer}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
