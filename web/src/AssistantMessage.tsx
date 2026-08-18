import type { ChatResponse } from "./types";

function linkify(text: string) {
  const parts = text.split(/(https?:\/\/[^\s<>\]]+)/g);
  return parts.map((part, i) => {
    if (part.startsWith("http://") || part.startsWith("https://")) {
      const url = part.replace(/[.,;)]+$/, "");
      return (
        <a
          key={`${url}-${i}`}
          href={url}
          target="_blank"
          rel="noreferrer"
          className="text-primary-container underline underline-offset-2"
        >
          {url}
        </a>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function fieldLabel(field: string | null): string {
  if (!field) return "Value";
  return field.replace(/_/g, " ");
}

export function AssistantMessage({ view }: { view: ChatResponse }) {
  const mixed = view.refusal_appended && Boolean(view.refusal_message);
  const showSchemes =
    view.intent === "unsupported_scheme" && view.supported_schemes.length === 5;
  const showTable = view.comparison_rows.length > 0;

  return (
    <div className="flex items-start gap-4 max-w-[90%] md:max-w-[95%]">
      <div className="w-8 h-8 rounded-full bg-surface-container-highest flex-shrink-0 flex items-center justify-center border border-outline-variant/50">
        <span className="material-symbols-outlined text-[18px] text-primary-container">
          smart_toy
        </span>
      </div>
      <div className="flex flex-col gap-3 min-w-0 flex-1">
        {mixed ? (
          <div className="bg-[#12141A] border border-white/10 rounded-2xl rounded-tl-sm p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-outline mb-2">
              Facts
            </p>
            <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
              {linkify(view.answer_text)}
            </p>
            <CitationsAndStamp view={view} />
          </div>
        ) : (
          <div className="bg-[#12141A] border border-white/10 rounded-2xl rounded-tl-sm p-4 md:p-5">
            {showTable ? (
              <>
                <div className="flex items-center gap-2 mb-3 text-on-surface-variant">
                  <span className="material-symbols-outlined text-primary-container">
                    insights
                  </span>
                  <span className="text-xs font-medium uppercase tracking-wider">
                    Comparison
                  </span>
                </div>
                <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap mb-4">
                  {linkify(view.answer_text)}
                </p>
                <div className="overflow-x-auto rounded-lg border border-outline-variant">
                  <table className="w-full text-left border-collapse min-w-[520px]">
                    <thead>
                      <tr className="bg-surface-container-lowest/80 border-b border-outline-variant text-on-surface-variant text-[10px] font-semibold uppercase tracking-wider">
                        <th className="p-3 sticky left-0 bg-surface-container-lowest z-10">
                          Scheme
                        </th>
                        <th className="p-3 text-right">{fieldLabel(view.comparison_field)}</th>
                        <th className="p-3 text-center">Source</th>
                      </tr>
                    </thead>
                    <tbody className="text-sm divide-y divide-white/5">
                      {view.comparison_rows.map((row) => (
                        <tr key={row.scheme_id} className="hover:bg-surface-container-low">
                          <td className="p-3 sticky left-0 bg-[#12141A] border-r border-white/5 text-xs">
                            {row.scheme_name}
                          </td>
                          <td className="p-3 text-right font-mono text-xs">
                            {row.available && row.value
                              ? row.value
                              : "Unavailable from sources"}
                          </td>
                          <td className="p-3 text-center">
                            {row.source_url ? (
                              <a
                                href={row.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-flex text-primary-container"
                                aria-label={`Source for ${row.scheme_name}`}
                              >
                                <span className="material-symbols-outlined text-sm">
                                  open_in_new
                                </span>
                              </a>
                            ) : (
                              "—"
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <CitationsAndStamp view={view} hideIfInBody />
              </>
            ) : (
              <>
                {showSchemes ? (
                  <>
                    <p className="mb-4 text-sm text-on-surface-variant leading-relaxed whitespace-pre-wrap">
                      {linkify(view.answer_text)}
                    </p>
                    <ul className="flex flex-col gap-2 m-0 p-0 list-none">
                      {view.supported_schemes.map((name) => (
                        <li key={name} className="flex items-start gap-3">
                          <span className="material-symbols-outlined text-primary text-[14px] mt-0.5">
                            fiber_manual_record
                          </span>
                          <span className="text-xs font-medium text-on-surface">
                            {name}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="text-sm text-on-surface leading-relaxed whitespace-pre-wrap">
                    {linkify(view.answer_text)}
                  </p>
                )}
                <CitationsAndStamp view={view} />
              </>
            )}
          </div>
        )}
        {mixed && view.refusal_message ? (
          <div className="bg-[#171A22] border-l-4 border-tertiary-container rounded-r-lg p-3 flex gap-3 items-start">
            <span className="material-symbols-outlined text-tertiary-container flex-shrink-0 mt-0.5">
              gavel
            </span>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              {view.refusal_message}
            </p>
          </div>
        ) : null}
        {view.intent === "advisory" ? (
          <div className="sr-only">Advisory refusal</div>
        ) : null}
      </div>
    </div>
  );
}

function CitationsAndStamp({
  view,
  hideIfInBody = false,
}: {
  view: ChatResponse;
  hideIfInBody?: boolean;
}) {
  const stampInBody = (view.answer_text || "").toLowerCase().includes(
    "last updated from sources:",
  );
  return (
    <>
      {view.citations.length > 0 ? (
        <div className="flex flex-wrap gap-2 pt-3 mt-3 border-t border-outline-variant/50">
          {view.citations.map((c) => (
            <a
              key={c.url}
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 bg-surface-container py-1 px-2 rounded-full border border-outline-variant hover:border-primary-container group"
            >
              <span className="material-symbols-outlined text-[14px] text-on-surface-variant group-hover:text-primary-container">
                description
              </span>
              <span className="text-[11px] font-semibold text-on-surface-variant group-hover:text-primary-container group-hover:underline">
                {c.title}
              </span>
            </a>
          ))}
        </div>
      ) : null}
      {view.last_updated_from_sources && !(hideIfInBody && stampInBody) && !stampInBody ? (
        <p className="mt-2 text-[11px] text-on-surface-variant">
          Last updated from sources: {view.last_updated_from_sources}
        </p>
      ) : null}
    </>
  );
}
