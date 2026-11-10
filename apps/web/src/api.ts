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
  mode?: string;
  mobility_source?: string | null;
  noise_source?: string | null;
  user_count?: number | null;
  algorithm?: string;
  budget?: number;
  label?: string | null;
  named_city?: string | null;
  future_hidden?: boolean;
  evaluation_only: boolean;
  warning: string;
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
