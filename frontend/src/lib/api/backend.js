import { DEFAULT_BACKEND_URL } from "@/lib/constants";

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

export function getBackendBaseUrl() {
  return trimTrailingSlash(
    process.env.INTENTSHELF_BACKEND_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      DEFAULT_BACKEND_URL,
  );
}

export function buildBackendUrl(pathname, searchParams) {
  const url = new URL(pathname, `${getBackendBaseUrl()}/`);

  if (searchParams) {
    for (const [key, value] of searchParams.entries()) {
      url.searchParams.set(key, value);
    }
  }

  return url;
}

export async function fetchBackend(pathname, init = {}) {
  const headers = new Headers(init.headers || {});

  if (init.body && !headers.has("content-type")) {
    headers.set("content-type", "application/json");
  }

  return fetch(buildBackendUrl(pathname), {
    ...init,
    headers,
    cache: "no-store",
  });
}

export async function readJsonSafely(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}
