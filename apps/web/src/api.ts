export type Role = "admin" | "publisher" | "collector";

export type User = { id: number; username: string; display_name: string; role: Role };

export type Frame = {
  width: number;
  height: number;
  slot: number;
  slot_label: string;
  coordinate_system: string;
  data_origin: string;
  real_city: boolean;
  evaluation_only: boolean;
  warning: string;
  anonymous?: boolean;
  basemap?: string | null;
  cells: { x: number; y: number; zone: string; prediction: number; uncertainty: number; truth?: number }[];
  participants: { id: number; name: string; kind: string; x: number; y: number; online: boolean }[];
  observations: { x: number; y: number; db: number; source: string }[];
  tasks: { id: number; x: number; y: number; status: string; title: string }[];
};

const TOKEN_KEY = "unlab-token";

export function token() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(value: string | null) {
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const current = token();
  if (current) headers.set("Authorization", `Bearer ${current}`);
  const response = await fetch(path, { ...init, headers });
  const type = response.headers.get("content-type") || "";
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      message = body.error?.message || message;
    } catch {
      message = await response.text();
    }
    throw new ApiError(response.status, message);
  }
  if (type.includes("text/csv")) return (await response.text()) as T;
  return (await response.json()) as T;
}

export type ScenarioMode = "synthetic_demo" | "real_mobility" | "real_noise" | "mixed_experiment" | "fully_real";

export const SCENARIO_MODES: { id: ScenarioMode; label: string }[] = [
  { id: "synthetic_demo", label: "Synthetic Demo" },
  { id: "real_mobility", label: "Real Mobility" },
  { id: "real_noise", label: "Real Noise" },
  { id: "mixed_experiment", label: "Mixed Experiment" },
  { id: "fully_real", label: "Fully Real" },
];

export type ManifestItem = {
  id?: string;
  name?: string;
  kind?: string;
  regime?: string;
  download_status?: string | null;
  preprocess_status?: string | null;
  license?: string | null;
  user_count?: number | null;
  station_count?: number | null;
  time_start?: string | null;
  time_end?: string | null;
  time_span?: string | null;
  spatial_span?: string | null;
  quality_flags?: unknown;
};

export type ManifestReport = {
  present: boolean;
  path: string;
  view: "download" | "preprocess";
  items: ManifestItem[];
  parse_error?: boolean;
  message: string | null;
};

export type Phase2File = {
  name: string;
  payload?: unknown;
  parse_error?: boolean;
  skipped?: boolean;
  bytes?: number;
};

export type Phase2Report = {
  present: boolean;
  path: string;
  files: Phase2File[];
  message: string | null;
};

export type DatasetRow = {
  id: number;
  kind: string;
  name: string;
  source: string;
  license: string;
  is_synthetic: boolean;
  regime: ScenarioMode | string;
  regime_label: string;
  real_city: boolean;
  coordinate_system: string;
  record_count: number;
  user_count?: number;
  time_start: string;
  time_end: string;
  spatial_desc: string;
  missing_rate: number;
  status: string;
  notes: string;
  quality: Record<string, unknown>;
};

export async function download(path: string, filename: string) {
  const text = await api<string>(path);
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
