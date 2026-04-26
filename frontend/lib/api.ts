const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`Ошибка API: ${response.status}`);
  }

  return (await response.json()) as T;
}

export const api = {
  getHealth: <T>() => getJson<T>("/health"),
  getLab1Status: <T>() => getJson<T>("/lab1/status"),
  getLab2Demo: <T>() => getJson<T>("/lab2/demo"),
  getLab3Status: <T>() => getJson<T>("/lab3/status")
};

