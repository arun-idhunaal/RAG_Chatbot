import type { ChatResponse, HealthResponse, UiConfig } from "./types";

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function fetchUiConfig(): Promise<UiConfig> {
  const res = await fetch("/v1/ui-config");
  if (!res.ok) throw new Error("Failed to load UI config");
  return res.json();
}

export async function sendChat(
  message: string,
  priorSchemeId?: string | null,
): Promise<ChatResponse> {
  const res = await fetch("/v1/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      prior_scheme_id: priorSchemeId || undefined,
    }),
  });
  if (!res.ok) throw new Error("Chat request failed");
  return res.json();
}
