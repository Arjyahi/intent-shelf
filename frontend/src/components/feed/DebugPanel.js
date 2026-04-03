"use client";

import { formatSourceLabel } from "@/lib/products";

const SOURCE_COPY = {
  collaborative:
    "Patterns from nearby shopper taste are helping surface adjacent pieces.",
  content: "A visually related anchor piece is pulling in similar styles.",
  fallback: "A broader discovery pass is keeping the mix fresh and balanced.",
  search: "A live query is pulling closer matches into the feed.",
  session: "Recent browsing is nudging the mix toward what you opened lately.",
};

function shortenId(value) {
  if (!value) {
    return "Unavailable";
  }

  if (value.length <= 18) {
    return value;
  }

  return `${value.slice(0, 8)}...${value.slice(-6)}`;
}

function getSignalCopy(summary) {
  return SOURCE_COPY[summary.source] || "This signal is helping shape the current mix.";
}

export default function DebugPanel({
  activeSearchQuery,
  cartCount,
  feedResponse,
  likeCount,
  saveCount,
  selectedStrategyName,
  session,
  sessionEvents,
}) {
  const sourceSummaries = feedResponse?.source_summaries || [];
  const activeSources = sourceSummaries.filter(
    (summary) => summary.used && summary.returned_count > 0,
  );
  const shopperSignalSources = activeSources.filter((summary) => summary.source !== "session");
  const sessionSignalCount = sessionEvents.length + likeCount + saveCount;

  return (
    <section className="signal-panel">
      <p className="hero-kicker">What&apos;s shaping your feed</p>
      <h3 className="signal-panel__title">Current feed signals</h3>
      <p className="signal-panel__copy">
        Recommendation style sets the tone. Active feed signals show what is
        actually influencing this mix right now.
      </p>

      <div className="signals-grid">
        <article className="signal-card signal-card--accent">
          <span className="signal-card__label">Recommendation style</span>
          <strong className="signal-card__value">{selectedStrategyName}</strong>
          <p className="signal-card__copy">
            Choose how recommendations adapt without changing the rest of your
            browsing flow.
          </p>
        </article>

        {sessionSignalCount ? (
          <article className="signal-card">
            <span className="signal-card__label">Recent activity</span>
            <strong className="signal-card__value">{sessionSignalCount} live signals</strong>
            <p className="signal-card__copy">
              Recent taps, likes, and saves are steering the feed toward what
              you&apos;re exploring right now.
            </p>
          </article>
        ) : null}

        {shopperSignalSources.map((summary) => (
          <article key={summary.source} className="signal-card">
            <span className="signal-card__label">{formatSourceLabel(summary.source)}</span>
            <strong className="signal-card__value">
              {summary.returned_count} looks in the mix
            </strong>
            <p className="signal-card__copy">{getSignalCopy(summary)}</p>
          </article>
        ))}

        {!sessionSignalCount && !shopperSignalSources.length ? (
          <article className="signal-card">
            <span className="signal-card__label">Fresh discovery</span>
            <strong className="signal-card__value">A lighter starting mix</strong>
            <p className="signal-card__copy">
              As you browse, save, and open more pieces, the feed will adapt and
              sharpen.
            </p>
          </article>
        ) : null}
      </div>

      {activeSources.length ? (
        <div className="signal-tags">
          {activeSources.map((summary) => (
            <span key={summary.source} className="reason-tag">
              {formatSourceLabel(summary.source)}
            </span>
          ))}
        </div>
      ) : null}

      <details className="developer-panel">
        <summary className="developer-panel__summary">Developer details</summary>
        <p className="debug-panel__copy">
          Raw request diagnostics stay here so the main utility view remains
          shopper-facing.
        </p>

        <div className="debug-grid">
          <div className="debug-grid__item">
            <span className="debug-grid__label">Session</span>
            <span className="debug-grid__value">{shortenId(session.session_id)}</span>
          </div>
          <div className="debug-grid__item">
            <span className="debug-grid__label">Activity</span>
            <span className="debug-grid__value">
              {sessionEvents.length} events / {likeCount} likes / {saveCount} saves
            </span>
          </div>
          <div className="debug-grid__item">
            <span className="debug-grid__label">Bag</span>
            <span className="debug-grid__value">{cartCount} items</span>
          </div>
          <div className="debug-grid__item">
            <span className="debug-grid__label">Search view</span>
            <span className="debug-grid__value">
              {activeSearchQuery ? `${activeSearchQuery} (separate from feed)` : "Inactive"}
            </span>
          </div>
        </div>

        <div className="debug-columns">
          <div className="debug-list">
            <h3 className="debug-list__title">Source summaries</h3>
            {sourceSummaries.map((summary) => (
              <div key={summary.source} className="debug-list__item">
                <strong>{summary.source}</strong>
                <p className="debug-list__meta">
                  Requested: {String(summary.requested)} / Used: {String(summary.used)} / Returned:{" "}
                  {summary.returned_count}
                  {summary.skip_reason ? ` / ${summary.skip_reason}` : ""}
                </p>
              </div>
            ))}
          </div>

          <div className="debug-list">
            <h3 className="debug-list__title">Recent events</h3>
            {sessionEvents.slice(0, 6).map((event) => (
              <div key={event.event_id} className="debug-list__item">
                <strong>{event.event_type}</strong>
                <p className="debug-list__meta">
                  {event.source_surface} / {shortenId(event.product_id)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </details>
    </section>
  );
}
