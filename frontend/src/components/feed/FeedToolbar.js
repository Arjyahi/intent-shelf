"use client";

import SearchBar from "@/components/search/SearchBar";
import { Glyph } from "@/components/ui/IconButton";

export default function FeedToolbar({
  currentStrategyName,
  isSearching,
  onOpenUtilityPanel,
  onQueryChange,
  onSearchReset,
  onSearchSubmit,
  queryValue,
}) {
  return (
    <section className="toolbar-shell toolbar-shell--inline">
      <div className="toolbar-block toolbar-block--search">
        <p className="hero-kicker">Search the catalog</p>
        <p className="toolbar-copy">
          Search styles, color stories, and silhouettes without leaving your
          discovery flow.
        </p>
        <SearchBar
          isLoading={isSearching}
          onChange={onQueryChange}
          onReset={onSearchReset}
          onSubmit={onSearchSubmit}
          value={queryValue}
        />
      </div>

      <div className="toolbar-block toolbar-block--utility">
        <p className="hero-kicker">
          <Glyph name="sliders" /> Shape your feed
        </p>
        <p className="toolbar-copy">
          Choose how recommendations adapt, then open a lighter utility view for
          feed controls and current signals.
        </p>
        <div className="toolbar-summary">
          <div className="toolbar-summary__card">
            <span className="toolbar-summary__label">Recommendation style</span>
            <strong className="toolbar-summary__value">{currentStrategyName}</strong>
            <p className="toolbar-summary__copy">
              Choose how recommendations adapt while the feed stays center stage.
            </p>
          </div>
          <button
            type="button"
            className="secondary-button toolbar-summary__action"
            onClick={onOpenUtilityPanel}
          >
            <Glyph name="sliders" />
            <span>Open feed controls</span>
          </button>
        </div>
      </div>
    </section>
  );
}
