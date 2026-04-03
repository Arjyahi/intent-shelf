"use client";

import { startTransition, useEffect, useState } from "react";

import CartDrawer from "@/components/cart/CartDrawer";
import FeedGrid from "@/components/feed/FeedGrid";
import FeedToolbar from "@/components/feed/FeedToolbar";
import FeedUtilityDrawer from "@/components/feed/FeedUtilityDrawer";
import LibraryDrawer from "@/components/library/LibraryDrawer";
import ProductDetailModal from "@/components/product/ProductDetailModal";
import { Glyph } from "@/components/ui/IconButton";
import {
  fetchFeed,
  fetchRankingStrategies,
  fetchSearchResults,
  fetchSimilarProducts,
} from "@/lib/api/client";
import {
  DEFAULT_APP_NAME,
  DEFAULT_RANKING_STRATEGY,
  FEED_BATCH_SIZE,
  SEARCH_BATCH_SIZE,
  SIMILAR_BATCH_SIZE,
} from "@/lib/constants";
import {
  formatSourceLabel,
  getPrimarySignal,
  mergeProductContext,
  normalizeFeedProduct,
  normalizeSearchProduct,
  normalizeSimilarProduct,
} from "@/lib/products";
import { useAppState } from "@/state/AppStateContext";

const THEME_STORAGE_KEY = "intentshelf.theme";

function buildFeedPayload(appState) {
  return {
    user_id: appState.userId,
    ranking_strategy: appState.selectedStrategy,
    session: appState.session,
    session_events: appState.sessionEvents,
    like_events: appState.likeEvents,
    save_events: appState.saveEvents,
    blended_k: FEED_BATCH_SIZE,
    reranked_k: 24,
    explanation_options: {
      include_evidence: true,
      max_supporting_reasons: 2,
    },
  };
}

export default function DiscoveryExperience() {
  const appState = useAppState();
  const {
    actions,
    cartCount,
    cartItems,
    cartProductIds,
    isCartOpen,
    isHydrated,
    likeEvents,
    likedItems,
    likedProductIds,
    saveEvents,
    savedItems,
    savedProductIds,
    selectedStrategy,
    session,
    sessionEvents,
    userId,
  } = appState;

  const [strategies, setStrategies] = useState([]);
  const [feedResponse, setFeedResponse] = useState(null);
  const [feedStatus, setFeedStatus] = useState("idle");
  const [feedError, setFeedError] = useState("");
  const [feedReloadToken, setFeedReloadToken] = useState(0);

  const [searchInput, setSearchInput] = useState("");
  const [activeSearchQuery, setActiveSearchQuery] = useState("");
  const [searchResponse, setSearchResponse] = useState(null);
  const [searchStatus, setSearchStatus] = useState("idle");
  const [searchError, setSearchError] = useState("");
  const [isUtilityOpen, setIsUtilityOpen] = useState(false);
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [libraryTab, setLibraryTab] = useState("saved");
  const [theme, setTheme] = useState("light");

  const [activeProduct, setActiveProduct] = useState(null);
  const [similarResponse, setSimilarResponse] = useState(null);
  const [similarStatus, setSimilarStatus] = useState("idle");
  const [similarError, setSimilarError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadStrategies() {
      try {
        const response = await fetchRankingStrategies();

        if (!cancelled) {
          setStrategies(response.strategies || []);
        }
      } catch {
        if (!cancelled) {
          setStrategies([]);
        }
      }
    }

    loadStrategies();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    const resolvedTheme =
      storedTheme ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

    setTheme(resolvedTheme);
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") {
      return;
    }

    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const feedSignalStamp = [
    userId,
    selectedStrategy,
    session.session_id,
    sessionEvents.slice(0, 8).map((event) => event.event_id).join(","),
    likeEvents.map((event) => event.product_id).join(","),
    saveEvents.map((event) => event.product_id).join(","),
  ].join("|");

  useEffect(() => {
    if (!isHydrated) {
      return undefined;
    }

    let cancelled = false;

    const timeoutId = window.setTimeout(async () => {
      try {
        setFeedStatus((current) => (current === "idle" ? "loading" : "refreshing"));
        setFeedError("");

        const response = await fetchFeed(buildFeedPayload(appState));

        if (!cancelled) {
          setFeedResponse(response);
          setFeedStatus("success");
        }
      } catch (error) {
        if (!cancelled) {
          setFeedError(error.message);
          setFeedStatus("error");
        }
      }
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [appState, feedReloadToken, feedSignalStamp, isHydrated]);

  useEffect(() => {
    if (!activeProduct?.productId) {
      setSimilarResponse(null);
      setSimilarStatus("idle");
      setSimilarError("");
      return undefined;
    }

    let cancelled = false;

    async function loadSimilarProducts() {
      try {
        setSimilarStatus("loading");
        setSimilarError("");

        const response = await fetchSimilarProducts(activeProduct.productId, {
          k: SIMILAR_BATCH_SIZE,
        });

        if (!cancelled) {
          setSimilarResponse(response);
          setSimilarStatus("success");
        }
      } catch (error) {
        if (!cancelled) {
          setSimilarError(error.message);
          setSimilarStatus("error");
        }
      }
    }

    loadSimilarProducts();

    return () => {
      cancelled = true;
    };
  }, [activeProduct]);

  const strategyDefinitions = strategies.length
    ? strategies
    : [
        {
          key: DEFAULT_RANKING_STRATEGY,
          name: "Default",
          description: "A balanced mix of familiar favorites and fresh discoveries.",
        },
      ];

  const resolvedStrategy =
    strategyDefinitions.find((strategy) => strategy.key === selectedStrategy) ||
    strategyDefinitions[0];

  const feedProducts = (feedResponse?.results || []).map(normalizeFeedProduct);
  const searchProducts = (searchResponse?.results || []).map((item) =>
    normalizeSearchProduct(item, activeSearchQuery),
  );
  const similarProducts = (similarResponse?.results || []).map(normalizeSimilarProduct);
  const knownProducts = [...feedProducts, ...searchProducts, ...similarProducts];

  const sessionSignalCount =
    sessionEvents.length + likeEvents.length + saveEvents.length;

  function handleSearchSubmit(nextQuery) {
    const normalizedQuery = nextQuery.trim();

    if (!normalizedQuery) {
      handleSearchReset();
      return;
    }

    setActiveSearchQuery(normalizedQuery);
    setSearchStatus("loading");
    setSearchError("");

    fetchSearchResults({
      query: normalizedQuery,
      k: SEARCH_BATCH_SIZE,
      sessionId: session.session_id,
      userId,
      strategyUsed: selectedStrategy,
    })
      .then((response) => {
        setSearchResponse(response);
        setSearchStatus("success");
      })
      .catch((error) => {
        setSearchResponse(null);
        setSearchStatus("error");
        setSearchError(error.message);
      });
  }

  function handleSearchReset() {
    setSearchInput("");
    setActiveSearchQuery("");
    setSearchResponse(null);
    setSearchStatus("idle");
    setSearchError("");
  }

  function openProduct(product, options = {}) {
    const enrichedProduct = mergeProductContext(product, knownProducts);

    actions.recordSessionEvent({
      eventType: options.eventType || "detail_open",
      productId: enrichedProduct.productId,
      rankPosition: options.rankPosition,
      sourceCandidateType: getPrimarySignal(enrichedProduct),
      surface: options.surface,
    });

    startTransition(() => {
      setActiveProduct(enrichedProduct);
    });
  }

  function openLibrary(tab) {
    setLibraryTab(tab);
    setIsLibraryOpen(true);
  }

  return (
    <main className="discovery-page">
      <div className="page-glow page-glow--one" />
      <div className="page-glow page-glow--two" />

      <header className="topbar">
        <div className="brand-lockup">
          <span className="brand-mark">IS</span>
          <div className="brand-text">
            <h1 className="brand-name">{DEFAULT_APP_NAME}</h1>
            <p className="brand-copy">
              Discover pieces shaped by what you search, save, and explore.
            </p>
          </div>
        </div>

        <div className="topbar__actions">
          <button
            type="button"
            className="surface-button surface-button--compact"
            onClick={() => openLibrary("saved")}
          >
            <Glyph name="bookmark" />
            <span>Saved</span>
            <span className="surface-button__count">{savedItems.length}</span>
          </button>

          <button
            type="button"
            className="surface-button surface-button--compact"
            onClick={() => openLibrary("liked")}
          >
            <Glyph name="heart" />
            <span>Liked</span>
            <span className="surface-button__count">{likedItems.length}</span>
          </button>

          <button
            type="button"
            className="surface-button"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
            onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
          >
            <Glyph name={theme === "dark" ? "sun" : "moon"} />
            <span>Theme</span>
          </button>

          <button type="button" className="surface-button" onClick={actions.openCart}>
            <Glyph name="bag" />
            <span>Bag</span>
            <span className="surface-button__count">{cartCount}</span>
          </button>
        </div>
      </header>

      <section className="hero-panel">
        <div className="hero-copy">
          <p className="hero-kicker">Curated for how you browse</p>
          <h2 className="hero-title">Discover fashion that moves with your taste.</h2>
          <p className="hero-lead">
            Explore a personalized stream of looks, search the catalog in one
            place, and open any piece to see similar styles and why it fits
            your feed.
          </p>
          <div className="hero-badges">
            <span className="pill pill--accent">Image-first discovery</span>
            <span className="pill pill--accent">Why you&apos;re seeing this</span>
            <span className="pill pill--accent">Save, like, and add to bag</span>
          </div>
        </div>

        <div className="hero-metrics">
          <article className="hero-stat">
            <span className="hero-stat__label">Active strategy</span>
            <span className="hero-stat__value">{resolvedStrategy.name}</span>
            <p className="hero-stat__copy">
              Switch between recommendation styles to keep the mix balanced,
              search-led, session-aware, or more varied.
            </p>
          </article>

          <article className="hero-stat">
            <span className="hero-stat__label">Your activity</span>
            <span className="hero-stat__value">{sessionSignalCount}</span>
            <p className="hero-stat__copy">
              Recent taps, likes, and saves help keep the feed in step with
              what you&apos;re browsing right now.
            </p>
          </article>

          <article className="hero-stat">
            <span className="hero-stat__label">Active feed signals</span>
            <span className="hero-stat__value">
              {feedResponse?.used_sources?.length || 0}
            </span>
            <p className="hero-stat__copy">
              {feedResponse?.used_sources?.length
                ? feedResponse.used_sources.map(formatSourceLabel).join(", ")
                : "Curating your next set of looks."}
            </p>
          </article>
        </div>
      </section>

      <FeedToolbar
        currentStrategyName={resolvedStrategy.name}
        isSearching={searchStatus === "loading"}
        onOpenUtilityPanel={() => setIsUtilityOpen(true)}
        onQueryChange={setSearchInput}
        onSearchReset={handleSearchReset}
        onSearchSubmit={handleSearchSubmit}
        queryValue={searchInput}
      />

      <div className="feed-stack">
        {activeSearchQuery || searchStatus !== "idle" ? (
          <FeedGrid
            cartProductIds={cartProductIds}
            copy="Explore results in the same visual browsing flow as your personalized feed."
            emptyActionLabel="Back to feed"
            emptyCopy="Try a different silhouette, occasion, or color phrase to pull more catalog matches."
            emptyTitle={`No results for "${activeSearchQuery}"`}
            error={searchError}
            errorCopy="Search is having trouble right now. Try again in a moment."
            errorTitle="We couldn't load your search"
            isLoading={searchStatus === "loading"}
            likedProductIds={likedProductIds}
            onAddToCart={actions.addToCart}
            onEmptyAction={handleSearchReset}
            onOpenProduct={(product, options) =>
              openProduct(product, {
                ...options,
                surface: "search_results",
              })
            }
            onRetry={() => handleSearchSubmit(activeSearchQuery)}
            onToggleLike={actions.toggleLike}
            onToggleSave={actions.toggleSave}
            products={searchProducts}
            savedProductIds={savedProductIds}
            sectionKicker="Search results"
            sectionTitle={`Results for "${activeSearchQuery}"`}
            statusLabel={
              searchStatus === "loading"
                ? "Searching the catalog"
                : searchStatus === "error"
                  ? "Search unavailable"
                  : `${searchProducts.length} results`
            }
            surfaceLabel="Search match"
          />
        ) : null}

        <FeedGrid
          cartProductIds={cartProductIds}
          copy="Discover looks tailored to what you&apos;re browsing, opening, liking, and saving right now."
          emptyCopy="Refresh in a moment to pull in a fresh set of looks."
          emptyTitle="The discovery feed is empty"
          error={feedError}
          errorCopy="Your discovery feed didn't refresh. Try again in a moment."
          errorTitle="We couldn't load your feed"
          isLoading={feedStatus === "loading" || feedStatus === "refreshing"}
          likedProductIds={likedProductIds}
          onAddToCart={actions.addToCart}
          onOpenProduct={(product, options) =>
            openProduct(product, {
              ...options,
              surface: "home_feed",
            })
          }
          onRetry={() => setFeedReloadToken((value) => value + 1)}
          onToggleLike={actions.toggleLike}
          onToggleSave={actions.toggleSave}
          products={feedProducts}
          savedProductIds={savedProductIds}
          sectionKicker="Personalized discovery"
          sectionTitle="For you"
          statusLabel={
            feedStatus === "refreshing"
              ? "Refreshing your latest mix"
              : feedStatus === "error"
                ? "Feed unavailable"
                : `${feedProducts.length} looks in view`
          }
          surfaceLabel="For you"
        />
      </div>

      <CartDrawer
        isOpen={isCartOpen}
        items={cartItems}
        onClear={actions.clearCart}
        onClose={actions.closeCart}
        onRemoveItem={actions.removeFromCart}
        onUpdateQuantity={actions.updateCartQuantity}
      />

      <LibraryDrawer
        activeTab={libraryTab}
        isOpen={isLibraryOpen}
        likedItems={likedItems}
        onAddToCart={actions.addToCart}
        onClose={() => setIsLibraryOpen(false)}
        onOpenItem={(product) => {
          setIsLibraryOpen(false);
          openProduct(product, {
            surface: libraryTab === "saved" ? "saved_library" : "liked_library",
          });
        }}
        onTabChange={setLibraryTab}
        onToggleLike={actions.toggleLike}
        onToggleSave={actions.toggleSave}
        savedItems={savedItems}
      />

      <FeedUtilityDrawer
        activeSearchQuery={activeSearchQuery}
        cartCount={cartCount}
        feedResponse={feedResponse}
        isOpen={isUtilityOpen}
        likeCount={likeEvents.length}
        onClose={() => setIsUtilityOpen(false)}
        onSelectStrategy={actions.setSelectedStrategy}
        saveCount={saveEvents.length}
        selectedStrategy={selectedStrategy}
        selectedStrategyName={resolvedStrategy.name}
        session={session}
        sessionEvents={sessionEvents}
        strategies={strategyDefinitions}
      />

      {activeProduct ? (
        <ProductDetailModal
          isInCart={cartProductIds.has(activeProduct.productId)}
          isLiked={likedProductIds.has(activeProduct.productId)}
          isSaved={savedProductIds.has(activeProduct.productId)}
          onAddToCart={actions.addToCart}
          onClose={() => setActiveProduct(null)}
          onSelectSimilar={(product, options) =>
            openProduct(product, {
              ...options,
              eventType: "similar_item_click",
              surface: "similar_items",
            })
          }
          onToggleLike={actions.toggleLike}
          onToggleSave={actions.toggleSave}
          product={activeProduct}
          similarError={similarError}
          similarLoading={similarStatus === "loading"}
          similarProducts={similarProducts}
        />
      ) : null}
    </main>
  );
}
