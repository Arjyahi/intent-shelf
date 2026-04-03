"use client";

import IconButton, { Glyph } from "@/components/ui/IconButton";
import EmptyState from "@/components/ui/EmptyState";
import { getProductFallbackGradient, getProductImageUrl } from "@/lib/images";
import { getProductSubtitle } from "@/lib/products";

function LibraryItem({
  isSavedTab,
  item,
  onAddToCart,
  onOpen,
  onToggleLike,
  onToggleSave,
}) {
  const imageUrl = getProductImageUrl(item.imagePath);

  return (
    <article className="cart-item library-item">
      <button
        type="button"
        className="library-item__open"
        onClick={() => onOpen?.(item)}
      >
        <div
          className="cart-item__media"
          style={{
            "--fallback-gradient": getProductFallbackGradient(item.productId),
          }}
        >
          {imageUrl ? <img alt={item.productName} src={imageUrl} /> : null}
        </div>
      </button>

      <div className="library-item__body">
        <button
          type="button"
          className="library-item__open library-item__open--text"
          onClick={() => onOpen?.(item)}
        >
          <h3 className="cart-item__title">{item.productName}</h3>
          <p className="cart-item__meta">{getProductSubtitle(item) || "Saved piece"}</p>
        </button>

        <div className="library-item__actions">
          <button type="button" className="ghost-button" onClick={() => onOpen?.(item)}>
            View
          </button>
          <button
            type="button"
            className="primary-button library-item__cta"
            onClick={() => onAddToCart?.(item)}
          >
            Add to bag
          </button>
          <IconButton
            active
            aria-label={isSavedTab ? "Remove from saved" : "Remove from liked"}
            icon={isSavedTab ? "bookmark" : "heart"}
            variant="compact"
            onClick={() =>
              isSavedTab ? onToggleSave?.(item) : onToggleLike?.(item)
            }
          />
        </div>
      </div>
    </article>
  );
}

export default function LibraryDrawer({
  activeTab,
  isOpen,
  likedItems,
  onAddToCart,
  onClose,
  onOpenItem,
  onTabChange,
  onToggleLike,
  onToggleSave,
  savedItems,
}) {
  if (!isOpen) {
    return null;
  }

  const isSavedTab = activeTab === "saved";
  const items = isSavedTab ? savedItems : likedItems;
  const title = isSavedTab ? "Saved" : "Liked";
  const intro = isSavedTab
    ? "Keep the styles you want to revisit in one polished place."
    : "Track the pieces that caught your eye and come back to them anytime.";

  return (
    <div className="drawer-shell" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close library"
        className="drawer-shell__backdrop"
        onClick={onClose}
      />

      <aside className="library-drawer">
        <div className="drawer__topbar">
          <div>
            <p className="hero-kicker">Your library</p>
            <h2 className="feed-section__title">{title}</h2>
          </div>
          <IconButton aria-label="Close library drawer" icon="close" onClick={onClose} />
        </div>

        <p className="drawer__intro">{intro}</p>

        <div className="library-tabs" role="tablist" aria-label="Library sections">
          <button
            type="button"
            role="tab"
            aria-selected={isSavedTab}
            className={`library-tab ${isSavedTab ? "is-active" : ""}`}
            onClick={() => onTabChange?.("saved")}
          >
            <Glyph name="bookmark" />
            <span>Saved</span>
            <span className="surface-button__count">{savedItems.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isSavedTab}
            className={`library-tab ${!isSavedTab ? "is-active" : ""}`}
            onClick={() => onTabChange?.("liked")}
          >
            <Glyph name="heart" />
            <span>Liked</span>
            <span className="surface-button__count">{likedItems.length}</span>
          </button>
        </div>

        {items.length ? (
          <div className="drawer__list">
            {items.map((item) => (
              <LibraryItem
                key={`${activeTab}_${item.productId}`}
                isSavedTab={isSavedTab}
                item={item}
                onAddToCart={onAddToCart}
                onOpen={onOpenItem}
                onToggleLike={onToggleLike}
                onToggleSave={onToggleSave}
              />
            ))}
          </div>
        ) : (
          <EmptyState
            copy={
              isSavedTab
                ? "Save pieces from your feed or product detail view to build a personal shortlist."
                : "Like the styles that stand out to keep a quick runway of favorites."
            }
            title={isSavedTab ? "No saved pieces yet" : "No liked pieces yet"}
          />
        )}
      </aside>
    </div>
  );
}
