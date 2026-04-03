"use client";

import { createContext, useContext, useEffect, useState } from "react";

import {
  bootstrapRuntimeState,
  clearCartState,
  logSessionEvent,
  persistCartItem,
  persistLike,
  persistSave,
  removeCartItem,
  removeLike,
  removeSave,
  upsertSessionState,
} from "@/lib/api/persistence";
import {
  APP_STATE_STORAGE_KEY,
  DEFAULT_DEMO_USER_ID,
  DEFAULT_RANKING_STRATEGY,
  MAX_SESSION_EVENTS,
  MAX_SIGNAL_EVENTS,
} from "@/lib/constants";

const AppStateContext = createContext(null);

function buildId(prefix) {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, "")}`;
}

function buildSession(userId = DEFAULT_DEMO_USER_ID) {
  return {
    session_id: buildId("sess"),
    user_id: userId,
    session_start: new Date().toISOString(),
    entry_surface: "home_feed",
    source: "intentshelf_app",
  };
}

function buildEventBase(prefix) {
  return {
    event_id: buildId(prefix),
    event_timestamp: new Date().toISOString(),
    source: "intentshelf_app",
  };
}

function buildCartSnapshot(product, quantity = 1) {
  return {
    productId: product.productId,
    productName: product.productName,
    productTypeName: product.productTypeName,
    productGroupName: product.productGroupName,
    imagePath: product.imagePath,
    quantity,
  };
}

function buildCartItem(item) {
  return {
    productId: item.product_id,
    productName: item.product_name,
    productTypeName: item.product_type_name || null,
    productGroupName: item.product_group_name || null,
    imagePath: item.image_path || null,
    quantity: item.quantity,
  };
}

function buildLibrarySnapshot(product) {
  return {
    product_id: product.productId,
    product_name: product.productName,
    product_type_name: product.productTypeName || null,
    product_group_name: product.productGroupName || null,
    colour_group_name: product.colourGroupName || null,
    department_name: product.departmentName || null,
    image_path: product.imagePath || null,
    explanation: product.explanation || null,
    contributing_sources: product.contributingSources || [],
    discovery_source: product.discoverySource || null,
    search_query: product.searchQuery || null,
  };
}

function buildPersistenceSnapshot(product) {
  const snapshot = buildLibrarySnapshot(product);
  delete snapshot.product_id;
  return snapshot;
}

function buildLibraryItem(event) {
  return {
    productId: event.product_id,
    productName: event.product_name || "Fashion piece",
    productTypeName: event.product_type_name || null,
    productGroupName: event.product_group_name || null,
    colourGroupName: event.colour_group_name || null,
    departmentName: event.department_name || null,
    imagePath: event.image_path || null,
    explanation: event.explanation || null,
    contributingSources: event.contributing_sources || [],
    discoverySource: event.discovery_source || "feed",
    searchQuery: event.search_query || null,
  };
}

function limitRecent(items, maxItems) {
  return items.slice(0, maxItems);
}

function createInitialState() {
  return {
    userId: DEFAULT_DEMO_USER_ID,
    selectedStrategy: DEFAULT_RANKING_STRATEGY,
    session: buildSession(DEFAULT_DEMO_USER_ID),
    sessionEvents: [],
    likeEvents: [],
    saveEvents: [],
    cartItems: [],
    isCartOpen: false,
  };
}

function sanitizeLoadedState(payload) {
  const fallback = createInitialState();

  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  return {
    ...fallback,
    userId: payload.userId || fallback.userId,
    selectedStrategy: payload.selectedStrategy || fallback.selectedStrategy,
    session:
      payload.session?.session_id && payload.session?.session_start
        ? {
            ...fallback.session,
            ...payload.session,
            user_id: payload.session.user_id || payload.userId || fallback.userId,
          }
        : fallback.session,
    sessionEvents: Array.isArray(payload.sessionEvents)
      ? payload.sessionEvents.slice(0, MAX_SESSION_EVENTS)
      : [],
    likeEvents: Array.isArray(payload.likeEvents)
      ? payload.likeEvents.slice(0, MAX_SIGNAL_EVENTS)
      : [],
    saveEvents: Array.isArray(payload.saveEvents)
      ? payload.saveEvents.slice(0, MAX_SIGNAL_EVENTS)
      : [],
    cartItems: Array.isArray(payload.cartItems) ? payload.cartItems : [],
    isCartOpen: Boolean(payload.isCartOpen),
  };
}

function mergeBootstrapState(current, payload) {
  return {
    ...current,
    userId: payload.session?.user_id || current.userId,
    session: payload.session || current.session,
    sessionEvents: Array.isArray(payload.session_events)
      ? payload.session_events.slice(0, MAX_SESSION_EVENTS)
      : current.sessionEvents,
    likeEvents: Array.isArray(payload.like_events)
      ? payload.like_events.slice(0, MAX_SIGNAL_EVENTS)
      : current.likeEvents,
    saveEvents: Array.isArray(payload.save_events)
      ? payload.save_events.slice(0, MAX_SIGNAL_EVENTS)
      : current.saveEvents,
    cartItems: Array.isArray(payload.cart_items)
      ? payload.cart_items.map(buildCartItem)
      : current.cartItems,
  };
}

function buildActorContext(state) {
  return {
    sessionId: state.session.session_id,
    userId: state.userId,
  };
}

export function AppStateProvider({ children }) {
  const [state, setState] = useState(createInitialState);
  const [isHydrated, setIsHydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function hydrateState() {
      let baseState = createInitialState();

      try {
        const storedValue = window.localStorage.getItem(APP_STATE_STORAGE_KEY);

        if (storedValue) {
          baseState = sanitizeLoadedState(JSON.parse(storedValue));
        }
      } catch {
        baseState = createInitialState();
      }

      if (!cancelled) {
        setState(baseState);
        setIsHydrated(true);
      }

      try {
        await upsertSessionState(baseState.session);
        const payload = await bootstrapRuntimeState({
          sessionId: baseState.session.session_id,
          userId: baseState.userId,
        });

        if (!cancelled) {
          setState((current) => mergeBootstrapState(current, payload));
        }
      } catch {
        // Fall back to local state when the persistence layer is unavailable.
      }
    }

    hydrateState();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isHydrated) {
      return;
    }

    window.localStorage.setItem(APP_STATE_STORAGE_KEY, JSON.stringify(state));
  }, [isHydrated, state]);

  function setSelectedStrategy(strategyKey) {
    setState((current) => ({
      ...current,
      selectedStrategy: strategyKey || DEFAULT_RANKING_STRATEGY,
    }));
  }

  function recordSessionEvent({
    productId,
    surface,
    rankPosition,
    sourceCandidateType,
    eventType = "detail_open",
  }) {
    const nextEvent = {
      ...buildEventBase("sevt"),
      session_id: state.session.session_id,
      user_id: state.userId,
      event_type: eventType,
      source_surface: surface,
      product_id: productId,
      rank_position: rankPosition || null,
      source_candidate_type: sourceCandidateType || null,
      metadata: {},
    };

    setState((current) => ({
      ...current,
      sessionEvents: limitRecent(
        [nextEvent, ...current.sessionEvents],
        MAX_SESSION_EVENTS,
      ),
    }));

    logSessionEvent(nextEvent).catch(() => {});
  }

  function toggleLike(product) {
    const existing = state.likeEvents.find(
      (event) => event.product_id === product.productId,
    );

    if (existing) {
      setState((current) => ({
        ...current,
        likeEvents: current.likeEvents.filter(
          (event) => event.product_id !== product.productId,
        ),
      }));

      removeLike(product.productId, buildActorContext(state)).catch(() => {});
      return;
    }

    const nextEvent = {
      ...buildEventBase("like"),
      session_id: state.session.session_id,
      user_id: state.userId,
      ...buildLibrarySnapshot(product),
      product_id: product.productId,
    };

    setState((current) => ({
      ...current,
      likeEvents: limitRecent(
        [
          nextEvent,
          ...current.likeEvents.filter(
            (event) => event.product_id !== product.productId,
          ),
        ],
        MAX_SIGNAL_EVENTS,
      ),
    }));

    persistLike(product.productId, {
      session_id: state.session.session_id,
      user_id: state.userId,
      event_id: nextEvent.event_id,
      event_timestamp: nextEvent.event_timestamp,
      source: nextEvent.source,
      snapshot: buildPersistenceSnapshot(product),
    }).catch(() => {});
  }

  function toggleSave(product) {
    const existing = state.saveEvents.find(
      (event) => event.product_id === product.productId,
    );

    if (existing) {
      setState((current) => ({
        ...current,
        saveEvents: current.saveEvents.filter(
          (event) => event.product_id !== product.productId,
        ),
      }));

      removeSave(product.productId, buildActorContext(state)).catch(() => {});
      return;
    }

    const nextEvent = {
      ...buildEventBase("save"),
      session_id: state.session.session_id,
      user_id: state.userId,
      ...buildLibrarySnapshot(product),
      product_id: product.productId,
    };

    setState((current) => ({
      ...current,
      saveEvents: limitRecent(
        [
          nextEvent,
          ...current.saveEvents.filter(
            (event) => event.product_id !== product.productId,
          ),
        ],
        MAX_SIGNAL_EVENTS,
      ),
    }));

    persistSave(product.productId, {
      session_id: state.session.session_id,
      user_id: state.userId,
      event_id: nextEvent.event_id,
      event_timestamp: nextEvent.event_timestamp,
      source: nextEvent.source,
      snapshot: buildPersistenceSnapshot(product),
    }).catch(() => {});
  }

  function addToCart(product) {
    const existingItem = state.cartItems.find(
      (item) => item.productId === product.productId,
    );
    const nextQuantity = existingItem ? existingItem.quantity + 1 : 1;

    setState((current) => {
      const currentExistingItem = current.cartItems.find(
        (item) => item.productId === product.productId,
      );

      return {
        ...current,
        isCartOpen: true,
        cartItems: currentExistingItem
          ? current.cartItems.map((item) =>
              item.productId === product.productId
                ? {
                    ...item,
                    quantity: item.quantity + 1,
                  }
                : item,
            )
          : [buildCartSnapshot(product), ...current.cartItems],
      };
    });

    persistCartItem(product.productId, {
      session_id: state.session.session_id,
      user_id: state.userId,
      quantity: nextQuantity,
      snapshot: buildPersistenceSnapshot(product),
    }).catch(() => {});
  }

  function updateCartQuantity(productId, quantity) {
    const existingItem = state.cartItems.find((item) => item.productId === productId);

    setState((current) => ({
      ...current,
      cartItems:
        quantity <= 0
          ? current.cartItems.filter((item) => item.productId !== productId)
          : current.cartItems.map((item) =>
              item.productId === productId
                ? {
                    ...item,
                    quantity,
                  }
                : item,
            ),
    }));

    if (quantity <= 0) {
      removeCartItem(productId, buildActorContext(state)).catch(() => {});
      return;
    }

    if (!existingItem) {
      return;
    }

    persistCartItem(productId, {
      session_id: state.session.session_id,
      user_id: state.userId,
      quantity,
      snapshot: {
        product_name: existingItem.productName,
        product_type_name: existingItem.productTypeName || null,
        product_group_name: existingItem.productGroupName || null,
        image_path: existingItem.imagePath || null,
      },
    }).catch(() => {});
  }

  function removeFromCart(productId) {
    setState((current) => ({
      ...current,
      cartItems: current.cartItems.filter((item) => item.productId !== productId),
    }));

    removeCartItem(productId, buildActorContext(state)).catch(() => {});
  }

  function openCart() {
    setState((current) => ({
      ...current,
      isCartOpen: true,
    }));
  }

  function closeCart() {
    setState((current) => ({
      ...current,
      isCartOpen: false,
    }));
  }

  function clearCart() {
    setState((current) => ({
      ...current,
      cartItems: [],
    }));

    clearCartState(buildActorContext(state)).catch(() => {});
  }

  const likedProductIds = new Set(
    state.likeEvents.map((event) => event.product_id),
  );
  const savedProductIds = new Set(
    state.saveEvents.map((event) => event.product_id),
  );
  const likedItems = state.likeEvents.map(buildLibraryItem);
  const savedItems = state.saveEvents.map(buildLibraryItem);
  const cartProductIds = new Set(state.cartItems.map((item) => item.productId));
  const cartCount = state.cartItems.reduce(
    (total, item) => total + item.quantity,
    0,
  );

  return (
    <AppStateContext.Provider
      value={{
        ...state,
        isHydrated,
        likedProductIds,
        likedItems,
        savedProductIds,
        savedItems,
        cartProductIds,
        cartCount,
        actions: {
          addToCart,
          clearCart,
          closeCart,
          openCart,
          recordSessionEvent,
          removeFromCart,
          setSelectedStrategy,
          toggleLike,
          toggleSave,
          updateCartQuantity,
        },
      }}
    >
      {children}
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const context = useContext(AppStateContext);

  if (!context) {
    throw new Error("useAppState must be used within AppStateProvider.");
  }

  return context;
}
