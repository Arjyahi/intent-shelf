function normalizeErrorMessage(response, payload) {
  const detail = payload.detail || payload.message || "";

  if (response.status === 404 || /^not found$/i.test(detail.trim())) {
    return "We couldn't load this right now.";
  }

  if (response.status >= 500) {
    return "We couldn't load this right now.";
  }

  return detail || "We couldn't load this right now.";
}

async function requestJson(url, init = {}) {
  const response = await fetch(url, {
    ...init,
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(normalizeErrorMessage(response, payload));
  }

  return payload;
}

export function fetchFeed(payload) {
  return requestJson("/api/feed", {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function fetchSearchResults({
  query,
  k,
  sessionId,
  userId,
  strategyUsed,
}) {
  const params = new URLSearchParams();

  params.set("query", query);
  params.set("k", String(k));

  if (sessionId) {
    params.set("session_id", sessionId);
  }

  if (userId) {
    params.set("user_id", userId);
  }

  if (strategyUsed) {
    params.set("strategy_used", strategyUsed);
  }

  return requestJson(`/api/search?${params.toString()}`);
}

export function fetchSimilarProducts(productId, { k }) {
  const params = new URLSearchParams({
    k: String(k),
  });

  return requestJson(`/api/products/${productId}/similar?${params.toString()}`);
}

export function fetchRankingStrategies() {
  return requestJson("/api/ranking/strategies");
}
