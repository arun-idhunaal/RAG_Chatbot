import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth, fetchUiConfig, sendChat } from "./api";
import { AssistantMessage } from "./AssistantMessage";
import { Composer } from "./Composer";
import { Sidebar } from "./Sidebar";
import type { ChatTurn, HealthResponse, UiConfig } from "./types";

function newId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export default function App() {
  const [config, setConfig] = useState<UiConfig | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [menuOpen, setMenuOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const lastSchemeIdRef = useRef<string | null>(null);

  useEffect(() => {
    void Promise.all([fetchUiConfig(), fetchHealth()])
      .then(([cfg, h]) => {
        setConfig(cfg);
        setHealth(h);
      })
      .catch(() => {
        setHealth({
          ok: false,
          corpus_available: false,
          scheme_count: 0,
          general_count: 0,
          reason: "unreachable",
          message: "The knowledge base is currently unavailable.",
        });
      });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  const ask = useCallback(
    async (text: string) => {
      if (!config || busy) return;
      setBusy(true);
      const id = newId();
      setTurns((prev) => [...prev, { id, userText: text, assistant: null, loading: true }]);
      try {
        const assistant = await sendChat(text, lastSchemeIdRef.current);
        const userText =
          assistant.intent === "pii" ? config.pii_user_placeholder : text;
        if (assistant.scheme_id) {
          lastSchemeIdRef.current = assistant.scheme_id;
        } else if (
          assistant.intent === "cross_scheme_comparison" ||
          assistant.intent === "unsupported_scheme" ||
          assistant.intent === "pii" ||
          assistant.intent === "unavailable" ||
          (assistant.comparison_rows && assistant.comparison_rows.length > 0)
        ) {
          lastSchemeIdRef.current = null;
        }
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id
              ? { ...t, userText, assistant, loading: false }
              : t,
          ),
        );
      } catch {
        setTurns((prev) =>
          prev.map((t) =>
            t.id === id
              ? {
                  ...t,
                  loading: false,
                  assistant: {
                    intent: "unavailable",
                    answer_text:
                      "The knowledge base is currently unavailable. Please try again after the next data refresh. I cannot answer from memory or invent fund facts.",
                    refusal_message: null,
                    refusal_appended: false,
                    citations: [],
                    last_updated_from_sources: null,
                    supported_schemes: [],
                    comparison_field: null,
                    comparison_rows: [],
                    insufficient_context: true,
                    corpus_available: false,
                    scheme_id: null,
                  },
                }
              : t,
          ),
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, config],
  );

  const empty = turns.length === 0;
  const corpusDown = health && !health.corpus_available;
  const disclaimer = config?.disclaimer ?? "Facts-only. No investment advice.";

  return (
    <div className="bg-background text-on-surface h-screen overflow-hidden flex flex-col md:flex-row">
      <header className="md:hidden flex items-center justify-between px-6 h-16 shrink-0 bg-surface border-b border-outline-variant z-30">
        <div className="flex items-center gap-3">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setMenuOpen(true)}
            className="text-primary-container"
          >
            <span className="material-symbols-outlined">menu</span>
          </button>
          <h1 className="text-lg font-semibold">INDmoney MF FAQ</h1>
        </div>
      </header>

      <Sidebar
        schemes={config?.schemes ?? []}
        disclaimer={disclaimer}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        onClear={() => {
          lastSchemeIdRef.current = null;
          setTurns([]);
        }}
        onAskScheme={(name) => void ask(`What is the expense ratio of ${name}?`)}
      />

      <main className="flex-1 flex flex-col min-h-0 md:ml-[300px] bg-background">
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar flex justify-center">
          <div className="w-full max-w-[800px] px-4 md:px-6 py-8 flex flex-col gap-6">
            {corpusDown ? (
              <div className="bg-error-container/40 border border-error/40 text-error rounded-xl p-4 text-sm">
                {health?.message ||
                  "The knowledge base is currently unavailable. Please try again after the next data refresh."}
              </div>
            ) : null}

            {empty && config ? (
              <>
                <div className="flex items-start gap-4 max-w-[90%] md:max-w-[80%]">
                  <div className="w-8 h-8 rounded-full bg-surface-container-highest flex-shrink-0 flex items-center justify-center border border-outline-variant/50">
                    <span className="material-symbols-outlined text-[18px] text-primary-container">
                      smart_toy
                    </span>
                  </div>
                  <div className="bg-[#12141A] border border-white/10 rounded-2xl rounded-tl-sm p-4">
                    {config.welcome_message.split("\n\n").map((para) => (
                      <p
                        key={para.slice(0, 24)}
                        className="text-sm text-on-surface leading-relaxed mb-2 last:mb-0"
                      >
                        {para.replace(/\*\*/g, "")}
                      </p>
                    ))}
                  </div>
                </div>
                <div className="mt-4 flex flex-col gap-3 items-center max-w-[600px] mx-auto w-full">
                  <span className="text-[10px] font-semibold text-outline uppercase tracking-widest mb-1">
                    Example queries
                  </span>
                  {config.example_questions.map((q, i) => (
                    <button
                      key={q}
                      type="button"
                      disabled={busy || Boolean(corpusDown)}
                      onClick={() => void ask(q)}
                      className="w-full text-left bg-[#12141A] border border-outline-variant/50 hover:border-primary-container/50 hover:bg-surface-container px-4 py-3 rounded-xl flex items-center gap-3 group disabled:opacity-50"
                    >
                      <span className="material-symbols-outlined text-outline group-hover:text-primary-container text-[20px]">
                        {i === 0 ? "search" : i === 1 ? "help_center" : "compare_arrows"}
                      </span>
                      <span className="text-sm text-on-surface-variant group-hover:text-on-surface">
                        {q}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            ) : null}

            {turns.map((turn) => (
              <div key={turn.id} className="flex flex-col gap-4">
                <div className="flex justify-end">
                  <div className="bg-surface-container-high text-on-surface px-4 py-3 rounded-2xl rounded-tr-sm max-w-[85%] text-sm border border-outline-variant/30">
                    {turn.userText}
                  </div>
                </div>
                {turn.loading ? (
                  <p className="text-xs text-on-surface-variant pl-12">
                    Looking up approved sources…
                  </p>
                ) : turn.assistant ? (
                  <AssistantMessage view={turn.assistant} />
                ) : null}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="shrink-0 w-full bg-background pt-2 pb-2 px-4 md:px-6 flex justify-center">
          <div className="w-full max-w-[800px]">
            <Composer disabled={busy || !config} onSend={(t) => void ask(t)} />
          </div>
        </div>

        <footer className="shrink-0 w-full py-1.5 flex justify-center items-center bg-surface-container-lowest border-t border-outline-variant/30">
          <span className="text-[11px] font-semibold text-on-surface-variant/80">
            {disclaimer}
          </span>
        </footer>
      </main>
    </div>
  );
}
