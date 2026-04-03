"use client";

export default function LoadingBlock() {
  return (
    <article className="loading-card" aria-hidden="true">
      <div className="loading-card__media" />
      <div className="loading-card__body">
        <div className="loading-card__line loading-card__line--short" />
        <div className="loading-card__line loading-card__line--medium" />
        <div className="loading-card__line loading-card__line--full" />
      </div>
    </article>
  );
}
