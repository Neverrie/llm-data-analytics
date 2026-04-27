const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8003/api";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store"
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Ошибка API: ${response.status}. ${errorText}`);
  }

  return (await response.json()) as T;
}

async function postJson<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store"
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Ошибка API: ${response.status}. ${errorText}`);
  }

  return (await response.json()) as TResponse;
}

async function postForm<TResponse>(path: string, formData: FormData): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store"
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Ошибка API: ${response.status}. ${errorText}`);
  }

  return (await response.json()) as TResponse;
}

export const api = {
  getHealth: <T>() => getJson<T>("/health"),
  getLab1Status: <T>() => getJson<T>("/lab1/status"),
  getLab2Status: <T>() => getJson<T>("/lab2/status"),
  getLab2SampleData: <T>(params: { limit?: number; min_score?: number | null; max_score?: number | null }) => {
    const search = new URLSearchParams();
    if (typeof params.limit === "number") search.set("limit", String(params.limit));
    if (typeof params.min_score === "number") search.set("min_score", String(params.min_score));
    if (typeof params.max_score === "number") search.set("max_score", String(params.max_score));
    const suffix = search.toString() ? `?${search.toString()}` : "";
    return getJson<T>(`/lab2/sample-data${suffix}`);
  },
  runLab2Pipeline: <TResponse, TBody>(body: TBody) => postJson<TResponse, TBody>("/lab2/run", body),
  getLab2Result: <T>() => getJson<T>("/lab2/result"),
  getLab3Status: <T>() => getJson<T>("/lab3/status"),
  getLab3Datasets: <T>() => getJson<T>("/lab3/datasets"),
  uploadLab3Dataset: <T>(file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return postForm<T>("/lab3/upload-dataset", formData);
  },
  getLab3Profile: <T>(datasetName: string) =>
    getJson<T>(`/lab3/profile?dataset_name=${encodeURIComponent(datasetName)}`),
  mapLab3Columns: <TResponse, TBody>(body: TBody) => postJson<TResponse, TBody>("/lab3/map-columns", body),
  getLab3Tools: <T>() => getJson<T>("/lab3/tools"),
  runLab3Tool: <TResponse, TBody>(body: TBody) => postJson<TResponse, TBody>("/lab3/run-tool", body),
  askLab3Agent: <TResponse, TBody>(body: TBody) => postJson<TResponse, TBody>("/lab3/ask", body),
  getLab3Result: <T>() => getJson<T>("/lab3/result")
};

export const apiBaseUrl = API_BASE_URL;
