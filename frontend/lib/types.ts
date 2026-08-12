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
  judge_model: string | null;
  analysis_json: Record<string, unknown>;
};
