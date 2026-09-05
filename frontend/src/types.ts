export interface ColumnProfile {
  name: string;
  dtype: string;
  missing_count: number;
  missing_pct: number;
  n_unique: number;
  semantic_type: "numeric" | "categorical" | "date";
  stats?: { min: number; max: number; mean: number; std: number; p25: number; p50: number; p75: number };
  top_values?: { value: string; count: number }[];
  min?: string;
  max?: string;
}

export interface DatasetProfile {
  n_rows: number;
  n_cols: number;
  duplicate_rows: number;
  duplicate_pct: number;
  missing_cells: number;
  columns: ColumnProfile[];
  numeric_columns: string[];
  categorical_columns: string[];
  date_columns: string[];
  likely_metric_columns: string[];
  likely_date_column: string | null;
}

export interface Suggestion {
  category: string;
  question: string;
}

export interface ProfileResponse {
  dataset_id: string;
  name: string;
  profile: DatasetProfile;
  suggestions: Suggestion[];
}

export interface ChartSpec {
  type: "stat" | "line" | "bar" | "scatter" | "table" | "empty";
  x_key?: string;
  y_key?: string;
  value_key?: string;
  columns?: string[];
  data?: Record<string, unknown>[];
}

export interface ExecutionStep {
  label: string;
  detail: string;
  status: "ok" | "retried" | "error";
}

export interface ChatResponse {
  answer: string;
  sql: string | null;
  chart: ChartSpec | null;
  facts: Record<string, unknown> | null;
  execution_trace: ExecutionStep[];
  execution_ms: number | null;
  low_confidence: boolean;
  error: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  response?: ChatResponse;
}
