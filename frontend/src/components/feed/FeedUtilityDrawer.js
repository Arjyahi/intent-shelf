"use client";

import { useEffect } from "react";

import DebugPanel from "@/components/feed/DebugPanel";
import IconButton from "@/components/ui/IconButton";

export default function FeedUtilityDrawer({
  activeSearchQuery,
  cartCount,
  feedResponse,
  isOpen,
  likeCount,
  onClose,
  onSelectStrategy,
  saveCount,
  selectedStrategy,
  selectedStrategyName,
  session,
  sessionEvents,
  strategies,
}) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }

    function handleEscape(event) {
      if (event.key === "Escape") {
        onClose?.();
      }
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  return (
    <div className="drawer-shell" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close feed controls"
        className="drawer-shell__backdrop"
        onClick={onClose}
      />

      <aside className="utility-drawer">
        <div className="drawer__topbar">
          <div>
            <p className="hero-kicker">Feed controls</p>
            <h2 className="feed-section__title">Shape your feed</h2>
          </div>
          <IconButton aria-label="Close feed controls" icon="close" onClick={onClose} />
        </div>

        <p className="drawer__intro">
          Choose how recommendations adapt, then glance at the signals shaping
          the current mix.
        </p>

        <section className="utility-drawer__section">
          <p className="hero-kicker">Recommendation style</p>
          <p className="toolbar-copy">
            Style selection guides the mix. Active feed signals show what is
            actually influencing the feed right now.
          </p>
          <div className="strategy-strip">
            {strategies.map((strategy) => (
              <button
                key={strategy.key}
                type="button"
                className={`strategy-pill ${
                  selectedStrategy === strategy.key ? "is-active" : ""
                }`}
                onClick={() => {
                  onSelectStrategy?.(strategy.key);
                  onClose?.();
                }}
              >
                <span className="strategy-pill__name">{strategy.name}</span>
                <p className="strategy-pill__copy">{strategy.description}</p>
              </button>
            ))}
          </div>
        </section>

        <DebugPanel
          activeSearchQuery={activeSearchQuery}
          cartCount={cartCount}
          feedResponse={feedResponse}
          likeCount={likeCount}
          saveCount={saveCount}
          selectedStrategyName={selectedStrategyName}
          session={session}
          sessionEvents={sessionEvents}
        />
      </aside>
    </div>
  );
}
