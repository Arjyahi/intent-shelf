"use client";

import { useState } from "react";

import IconButton, { Glyph } from "@/components/ui/IconButton";
import { getProductFallbackGradient, getProductImageUrl } from "@/lib/images";
import { getReasonPreview, getProductSubtitle } from "@/lib/products";

export default function ProductCard({
  isInCart,
  isLiked,
  isSaved,
  onAddToCart,
  onOpen,
  onToggleLike,
  onToggleSave,
  product,
  surfaceLabel,
}) {
  const [imageFailed, setImageFailed] = useState(false);

  const imageUrl = imageFailed ? null : getProductImageUrl(product.imagePath);
  const subtitle = getProductSubtitle(product);
  const reasonPreview = getReasonPreview(product);

  function handleAction(event, callback) {
    event.stopPropagation();
    callback?.(product);
  }

  return (
    <article className="product-card">
      <div className="product-card__actions">
        <IconButton
          active={isLiked}
          aria-label={isLiked ? "Unlike item" : "Like item"}
          icon="heart"
          onClick={(event) => handleAction(event, onToggleLike)}
        />
        <IconButton
          active={isSaved}
          aria-label={isSaved ? "Remove saved item" : "Save item"}
          icon="bookmark"
          onClick={(event) => handleAction(event, onToggleSave)}
        />
      </div>

      <button
        type="button"
        className="product-card__open"
        onClick={() => onOpen?.(product)}
      >
        <div
          className="product-card__media"
          style={{
            "--fallback-gradient": getProductFallbackGradient(product.productId),
          }}
        >
          {imageUrl ? (
            <img
              alt={product.productName}
              loading="lazy"
              src={imageUrl}
              onError={() => setImageFailed(true)}
            />
          ) : (
            <div className="product-card__fallback">
              <span>Featured pick</span>
            </div>
          )}
        </div>

        <div className="product-card__body">
          <div className="product-card__eyebrow">
            <span>{surfaceLabel}</span>
          </div>
          <h3 className="product-card__title">{product.productName}</h3>
          <p className="product-card__meta">{subtitle || "Fashion find"}</p>

          <div className="product-card__reason">
            <span className="product-card__reason-label">
              <Glyph name="sparkles" />
              Why this?
            </span>
            <p className="product-card__reason-copy">{reasonPreview}</p>
          </div>
        </div>
      </button>

      <div className="product-card__footer">
        <div className="product-card__cta">
          <span className="product-card__cta-copy">
            {isInCart ? "Waiting in your bag" : "Open to see the full story"}
          </span>
          <IconButton
            aria-label="Add to bag"
            icon="bag"
            label={isInCart ? "Add another" : "Add to bag"}
            variant="primary"
            onClick={(event) => handleAction(event, onAddToCart)}
          />
        </div>
      </div>
    </article>
  );
}
