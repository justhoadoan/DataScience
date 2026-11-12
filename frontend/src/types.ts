export type Category = "can_ho_chung_cu" | "nha_tro";
export type Schema = {
  categories: { value: Category; label: string }[];
  districts: string[];
  furnishing: { value: string; label: string }[];
  layout_policy: {
    shared_area_m2: number;
    area_per_separate_bedroom_m2: number;
    category_max_bedrooms: Record<Category, number>;
  };
  bedrooms_help: string;
};
export type Score = {
  n: number;
  mae_vnd: number;
  median_ae_vnd: number;
  r2: number;
  rmse_vnd: number;
};
export type District = {
  category: Category;
  district: string;
  n: number;
  median_vnd: number;
  q25_vnd: number;
  q75_vnd: number;
  area_median: number | null;
};
export type Market = {
  rows: number;
  eligible_rows: number;
  posting_start: string;
  posting_end: string;
  source_counts: Record<string, number>;
  districts: District[];
};
export type Model = {
  version: string;
  evaluated_at: string;
  selected_model: string;
  feature_schema: string[];
  benchmark: Score;
  category_metrics: Record<Category, Score>;
  development_n: number;
  internal_test_n: number;
  dataset: Omit<Market, "districts">;
  category_feature_schema: Record<Category, string[]>;
  behavior: {
    violations: number;
    checked_rows: number;
    contract_version: number;
  } | null;
};
export type Estimate = {
  prediction_vnd_month: number;
  model_version: string;
  warnings: string[];
  used_features: string[];
  historical_error: {
    mae_vnd: number;
    median_ae_vnd: number;
    n: number;
    note: string;
  };
  district_sample: District | null;
  scope_note: string;
  support: {
    nearby_training_n: number | null;
    bedroom_training_n: number | null;
    area_tolerance_m2: number | null;
    category_comparison: {
      category: Category;
      n: number;
      median_vnd: number | null;
      q25_vnd: number | null;
      q75_vnd: number | null;
    }[];
  };
};

export type Draft = {
  category: Category;
  district: string;
  area: string;
  bedrooms: string;
  furnishing: string;
};
