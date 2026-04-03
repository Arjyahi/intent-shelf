"use client";

import IconButton from "@/components/ui/IconButton";
import EmptyState from "@/components/ui/EmptyState";
import { getProductFallbackGradient, getProductImageUrl } from "@/lib/images";

function CartItem({ item, onRemove, onUpdateQuantity }) {
  const imageUrl = getProductImageUrl(item.imagePath);

  return (
    <article className="cart-item">
      <div
        className="cart-item__media"
        style={{
          "--fallback-gradient": getProductFallbackGradient(item.productId),
        }}
      >
        {imageUrl ? <img alt={item.productName} src={imageUrl} /> : null}
      </div>

      <div>
        <h3 className="cart-item__title">{item.productName}</h3>
        <p className="cart-item__meta">
          {[item.productTypeName, item.productGroupName].filter(Boolean).join(" / ") ||
            "Saved piece"}
        </p>

        <div className="cart-item__footer">
          <div className="quantity-stepper">
            <IconButton
              aria-label="Decrease quantity"
              icon="minus"
              variant="compact"
              onClick={() => onUpdateQuantity?.(item.productId, item.quantity - 1)}
            />
            <span className="quantity-stepper__value">{item.quantity}</span>
            <IconButton
              aria-label="Increase quantity"
              icon="plus"
              variant="compact"
              onClick={() => onUpdateQuantity?.(item.productId, item.quantity + 1)}
            />
          </div>

          <button
            type="button"
            className="ghost-button"
            onClick={() => onRemove?.(item.productId)}
          >
            Remove
          </button>
        </div>
      </div>
    </article>
  );
}

export default function CartDrawer({
  isOpen,
  items,
  onClear,
  onClose,
  onRemoveItem,
  onUpdateQuantity,
}) {
  if (!isOpen) {
    return null;
  }

  return (
    <div className="drawer-shell" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close cart"
        className="drawer-shell__backdrop"
        onClick={onClose}
      />

      <aside className="cart-drawer">
        <div className="drawer__topbar">
          <div>
            <p className="hero-kicker">Your picks</p>
            <h2 className="feed-section__title">Bag</h2>
          </div>
          <IconButton aria-label="Close cart drawer" icon="close" onClick={onClose} />
        </div>

        <p className="drawer__intro">
          Keep the pieces you want close while you browse and compare.
        </p>

        {items.length ? (
          <>
            <div className="drawer__list">
              {items.map((item) => (
                <CartItem
                  key={item.productId}
                  item={item}
                  onRemove={onRemoveItem}
                  onUpdateQuantity={onUpdateQuantity}
                />
              ))}
            </div>

            <div className="product-modal__actions">
              <button type="button" className="secondary-button" onClick={onClear}>
                Clear bag
              </button>
              <button type="button" className="primary-button" onClick={onClose}>
                Keep browsing
              </button>
            </div>
          </>
        ) : (
          <EmptyState
            copy="Add pieces from your feed or search results to keep them close while you browse."
            title="Your bag is empty"
          />
        )}
      </aside>
    </div>
  );
}
