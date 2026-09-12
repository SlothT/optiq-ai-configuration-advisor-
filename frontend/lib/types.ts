export type Project = {
  id: string;
  name: string;
  description?: string | null;
  created_at?: string | null;
};

export type ProviderView = {
  provider_name: string;
  configured: boolean;
  has_api_key: boolean;
  ollama_base_url?: string | null;
  status_message?: string | null;
  available_models: Array<{
    id: string;
    display_name: string;
    default_temperature: number;
    max_tokens: number;
    pricing: { input_per_1m: number; output_per_1m: number } | null;
  }>;
};

export type PromptAnalysis = {
  prompt_id: string;
  version: number;
  quality_score: number;
  strengths: string[];
  weaknesses: string[];
  suggested_improvements: string[];
  estimated_tokens: number;
  estimated_cost_usd: number;
  cost_is_local?: boolean;
  judge_model: string | null;
  analysis_json: Record<string, unknown>;
};

export type SavedPrompt = {
  id: string;
  project_id: string;
  source_prompt_id?: string | null;
  version: number;
  raw_text: string;
  task_type: string;
  quality_score: number;
  estimated_tokens: number;
  estimated_cost_usd: number;
  judge_model: string | null;
  analysis_json?: Record<string, unknown>;
  created_at?: string | null;
};

export type ExperimentRow = {
  model_id: string;
  provider?: string;
  prompt_id: string;
  prompt_version?: number;
  input_index: number;
  raw_output: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  cost_is_local?: boolean;
  quality_score?: number | null;
  accuracy?: number | null;
  answer_relevancy?: number | null;
  faithfulness?: number | null;
  error?: string | null;
  eval_engine?: string;
};

export type ExperimentSummary = {
  id: string;
  project_id: string;
  status: string;
  task_type: string;
  prompt_ids: string[];
  model_ids: string[];
  mlflow_run_id?: string | null;
  test_inputs?: Array<Record<string, unknown>> | null;
  results?: {
    rows?: ExperimentRow[];
    summary?: Record<string, number | null>;
    per_model?: Array<Record<string, unknown>>;
    label?: string;
    error?: string;
  } | null;
  created_at?: string | null;
};

export type RecommendationResult = {
  id: string;
  project_id: string;
  experiment_id?: string | null;
  recommended_config: Record<string, unknown>;
  ranked_options: Array<Record<string, unknown>>;
  excluded_options: Array<Record<string, unknown>>;
  justification: string;
};
