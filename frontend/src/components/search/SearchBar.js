"use client";

import { Glyph } from "@/components/ui/IconButton";

export default function SearchBar({
  isLoading,
  onChange,
  onReset,
  onSubmit,
  value,
}) {
  function handleSubmit(event) {
    event.preventDefault();
    onSubmit?.(value);
  }

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <Glyph name="search" />
      <label className="visually-hidden" htmlFor="catalog-search">
        Search the fashion catalog
      </label>
      <input
        id="catalog-search"
        className="search-bar__field"
        placeholder="Search dresses, denim, knits, or a color mood..."
        value={value}
        onChange={(event) => onChange?.(event.target.value)}
      />
      <div className="search-bar__actions">
        {value ? (
          <button type="button" className="ghost-button" onClick={onReset}>
            Clear
          </button>
        ) : null}
        <button type="submit" className="search-bar__submit">
          {isLoading ? "Searching..." : "Search"}
        </button>
      </div>
    </form>
  );
}
