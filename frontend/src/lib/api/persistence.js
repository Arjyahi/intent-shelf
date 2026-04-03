function normalizeErrorMessage(response, payload) {
  const detail = payload.detail || payload.message || "";

  if (response.status >= 500) {
    return "We couldn't save this right now.";
  }

  return detail || "We couldn't save this right now.";
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

function buildActorParams({ sessionId, userId, maxSessionEvents }) {
  const params = new URLSearchParams();

  if (sessionId) {
    params.set("session_id", sessionId);
  }

  if (userId) {
    params.set("user_id", userId);
  }

  if (maxSessionEvents) {
    params.set("max_session_events", String(maxSessionEvents));
  }

  return params;
}

export function bootstrapRuntimeState({ sessionId, userId, maxSessionEvents = 24 }) {
  const params = buildActorParams({
    sessionId,
    userId,
    maxSessionEvents,
  });

  return requestJson(`/api/state/bootstrap?${params.toString()}`);
}

export function upsertSessionState(session) {
  return requestJson(`/api/sessions/${session.session_id}`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(session),
  });
}

export function logSessionEvent(event) {
  return requestJson(`/api/sessions/${event.session_id}/events`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(event),
  });
}

export function persistLike(productId, payload) {
  return requestJson(`/api/likes/${productId}`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function removeLike(productId, { sessionId, userId }) {
  const params = buildActorParams({ sessionId, userId });
  return requestJson(`/api/likes/${productId}?${params.toString()}`, {
    method: "DELETE",
  });
}

export function persistSave(productId, payload) {
  return requestJson(`/api/saves/${productId}`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function removeSave(productId, { sessionId, userId }) {
  const params = buildActorParams({ sessionId, userId });
  return requestJson(`/api/saves/${productId}?${params.toString()}`, {
    method: "DELETE",
  });
}

export function persistCartItem(productId, payload) {
  return requestJson(`/api/cart/items/${productId}`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

export function removeCartItem(productId, { sessionId, userId }) {
  const params = buildActorParams({ sessionId, userId });
  return requestJson(`/api/cart/items/${productId}?${params.toString()}`, {
    method: "DELETE",
  });
}

export function clearCartState({ sessionId, userId }) {
  const params = buildActorParams({ sessionId, userId });
  return requestJson(`/api/cart?${params.toString()}`, {
    method: "DELETE",
  });
}
