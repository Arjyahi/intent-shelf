"use client";

import { useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import LoadingBlock from "@/components/ui/LoadingBlock";
import { getProductFallbackGradient, getProductImageUrl } from "@/lib/images";
import { getProductSubtitle } from "@/lib/products";

function SimilarCard({ index, onSelect, product }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = imageFailed ? null : getProductImageUrl(product.imagePath);

  return (
    <button
      type="button"
      className="similar-card"
      onClick={() =>
        onSelect?.(product, {
          rankPosition: index + 1,
        })
      }
    >
      <div
        className="similar-card__media"
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
        ) : null}
      </div>
      <div className="similar-card__body">
        <p className="similar-card__title">{product.productName}</p>
        <p className="similar-card__meta">
          {getProductSubtitle(product) || "Visually adjacent pick"}
        </p>
      </div>
    </button>
  );
}

export default function SimilarProductsRow({
  error,
  isLoading,
  onSelect,
  products,
}) {
  return (
    <section className="similar-row">
      <div className="similar-row__header">
        <div>
          <h3 className="similar-row__title">Similar items</h3>
          <p className="similar-row__copy">
            More styles with a similar feel, shape, or visual mood.
          </p>
        </div>
      </div>

      {error ? (
        <EmptyState
          copy="Similar styles are having trouble loading right now. Try another piece in a moment."
          title="Similar styles are unavailable right now"
        />
      ) : null}

      {!error && isLoading ? (
        <div className="similar-row__track">
          {Array.from({ length: 4 }).map((_, index) => (
            <LoadingBlock key={index} />
          ))}
        </div>
      ) : null}

      {!error && !isLoading && !products.length ? (
        <EmptyState
          copy="Open another piece to explore styles with a similar shape, texture, or mood."
          title="No similar styles yet"
        />
      ) : null}

      {products.length ? (
        <div className="similar-row__track">
          {products.map((product, index) => (
            <SimilarCard
              key={product.productId}
              index={index}
              onSelect={onSelect}
              product={product}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
