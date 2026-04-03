"use client";

import { useEffect, useState } from "react";

import ExplanationPanel from "@/components/explainability/ExplanationPanel";
import SimilarProductsRow from "@/components/product/SimilarProductsRow";
import IconButton from "@/components/ui/IconButton";
import { getProductFallbackGradient, getProductImageUrl } from "@/lib/images";
import { buildProductMetadata, getProductSubtitle } from "@/lib/products";

export default function ProductDetailModal({
  isInCart,
  isLiked,
  isSaved,
  onAddToCart,
  onClose,
  onSelectSimilar,
  onToggleLike,
  onToggleSave,
  product,
  similarError,
  similarLoading,
  similarProducts,
}) {
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
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
  }, [onClose]);

  const imageUrl = imageFailed ? null : getProductImageUrl(product.imagePath);
  const metadata = buildProductMetadata(product);

  return (
    <div className="modal-shell" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Close product detail"
        className="modal-shell__backdrop"
        onClick={onClose}
      />

      <div className="product-modal">
        <div
          className="product-modal__media"
          style={{
            "--fallback-gradient": getProductFallbackGradient(product.productId),
          }}
        >
          {imageUrl ? (
            <img
              alt={product.productName}
              src={imageUrl}
              onError={() => setImageFailed(true)}
            />
          ) : null}
        </div>

        <div className="product-modal__content">
          <div className="product-modal__topbar">
            <div>
              <p className="product-modal__eyebrow">Style spotlight</p>
            </div>
            <IconButton aria-label="Close detail panel" icon="close" onClick={onClose} />
          </div>

          <h2 className="product-modal__title">{product.productName}</h2>
          <p className="product-modal__subtitle">
            {getProductSubtitle(product) || "Chosen to fit your feed"}
          </p>

          <div className="product-modal__actions">
            <IconButton
              active={isLiked}
              icon="heart"
              label={isLiked ? "Liked" : "Like"}
              onClick={() => onToggleLike?.(product)}
            />
            <IconButton
              active={isSaved}
              icon="bookmark"
              label={isSaved ? "Saved" : "Save"}
              onClick={() => onToggleSave?.(product)}
            />
            <IconButton
              icon="bag"
              label={isInCart ? "Add another" : "Add to bag"}
              variant="primary"
              onClick={() => onAddToCart?.(product)}
            />
          </div>

          <ExplanationPanel product={product} />

          <section className="surface-card">
            <p className="product-modal__eyebrow">Style details</p>
            <div className="meta-grid">
              {metadata.map((item) => (
                <div key={item.label} className="meta-grid__item">
                  <span className="meta-grid__label">{item.label}</span>
                  <span className="meta-grid__value">{item.value}</span>
                </div>
              ))}
            </div>
          </section>

          <SimilarProductsRow
            error={similarError}
            isLoading={similarLoading}
            onSelect={onSelectSimilar}
            products={similarProducts}
          />
        </div>
      </div>
    </div>
  );
}
