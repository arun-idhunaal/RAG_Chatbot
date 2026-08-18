export type Citation = {
  title: string;
  url: string;
  page_ref: string | null;
};

export type ComparisonRow = {
  scheme_id: string;
  scheme_name: string;
  field: string;
  value: string | null;
  source_url: string;
  scraped_at: string;
  available: boolean;
};

export type ChatResponse = {
  intent: string;
  answer_text: string;
  refusal_message: string | null;
  refusal_appended: boolean;
  citations: Citation[];
  last_updated_from_sources: string | null;
  supported_schemes: string[];
  comparison_field: string | null;
  comparison_rows: ComparisonRow[];
  insufficient_context: boolean;
  corpus_available: boolean;
};

export type SchemeInfo = {
  scheme_id: string;
  canonical_name: string;
  source_url: string;
};

export type UiConfig = {
  disclaimer: string;
  welcome_message: string;
  example_questions: string[];
  pii_user_placeholder: string;
  schemes: SchemeInfo[];
};

export type HealthResponse = {
  ok: boolean;
  corpus_available: boolean;
  scheme_count: number;
  general_count: number;
  reason: string | null;
  message: string | null;
};

export type ChatTurn = {
  id: string;
  userText: string;
  assistant: ChatResponse | null;
  loading: boolean;
};
