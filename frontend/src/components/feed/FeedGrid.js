"use client";

import ProductCard from "@/components/product/ProductCard";
import EmptyState from "@/components/ui/EmptyState";
import LoadingBlock from "@/components/ui/LoadingBlock";

export default function FeedGrid({
  cartProductIds,
  copy,
  emptyActionLabel,
  emptyCopy,
  emptyTitle,
  error,
  errorCopy,
  errorTitle,
  isLoading,
  likedProductIds,
  onAddToCart,
  onEmptyAction,
  onOpenProduct,
  onRetry,
  onToggleLike,
  onToggleSave,
  products,
  savedProductIds,
  sectionKicker,
  sectionTitle,
  statusLabel,
  surfaceLabel,
}) {
  const hasProducts = products.length > 0;

  return (
    <section className="feed-section">
      <div className="feed-section__header">
        <div>
          <p className="feed-section__kicker">{sectionKicker}</p>
          <h2 className="feed-section__title">{sectionTitle}</h2>
          <p className="feed-section__copy">{copy}</p>
        </div>
        {statusLabel ? <div className="feed-section__status">{statusLabel}</div> : null}
      </div>

      {error && !hasProducts ? (
        <EmptyState
          actionLabel={onRetry ? "Retry" : null}
          copy={errorCopy || error}
          onAction={onRetry}
          title={errorTitle || "We couldn't load this right now"}
        />
      ) : null}

      {!error && !hasProducts && isLoading ? (
        <div className="feed-grid feed-grid--loading">
          {Array.from({ length: 8 }).map((_, index) => (
            <LoadingBlock key={index} />
          ))}
        </div>
      ) : null}

      {!error && !hasProducts && !isLoading ? (
        <EmptyState
          actionLabel={emptyActionLabel}
          copy={emptyCopy}
          onAction={onEmptyAction}
          title={emptyTitle}
        />
      ) : null}

      {hasProducts ? (
        <div className="feed-grid">
          {products.map((product, index) => (
            <ProductCard
              key={product.productId}
              isInCart={cartProductIds.has(product.productId)}
              isLiked={likedProductIds.has(product.productId)}
              isSaved={savedProductIds.has(product.productId)}
              onAddToCart={onAddToCart}
              onOpen={(item) =>
                onOpenProduct?.(item, {
                  rankPosition: index + 1,
                })
              }
              onToggleLike={onToggleLike}
              onToggleSave={onToggleSave}
              product={product}
              surfaceLabel={surfaceLabel}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
