"use client";

import {
  formatReasonTag,
  formatSourceLabel,
  getReasonPreview,
} from "@/lib/products";

export default function ExplanationPanel({ product }) {
  const explanation = product.explanation;
  const evidence = explanation?.evidence;
  const supportingReasons = explanation?.supportingReasons || [];
  const reasonTags = explanation?.reasonTags || [];

  if (!explanation && !product.searchQuery) {
    return null;
  }

  return (
    <section className="explanation-panel">
      <p className="product-modal__eyebrow">Why you&apos;re seeing this</p>
      <h3 className="explanation-panel__title">{getReasonPreview(product)}</h3>

      {supportingReasons.length ? (
        <ul className="explanation-panel__list">
          {supportingReasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : (
        <p className="explanation-panel__copy">
          We surface the strongest signals behind each recommendation so you can
          quickly understand what made this piece stand out.
        </p>
      )}

      <div className="tag-strip">
        {reasonTags.map((tag) => (
          <span key={tag} className="reason-tag">
            {formatReasonTag(tag)}
          </span>
        ))}
      </div>

      {evidence ? (
        <p className="explanation-panel__meta">
          Primary source: {formatSourceLabel(explanation.explanationSource)}.
          {evidence.meaningfulSources.length
            ? ` Supporting signals: ${evidence.meaningfulSources
                .map(formatSourceLabel)
                .join(", ")}.`
            : ""}
          {evidence.sessionContextUsed
            ? " Recent browsing actions also influenced this placement."
            : ""}
          {evidence.diversityPenalty
            ? " A diversity check helped keep the feed from collapsing into one repeated product type."
            : ""}
        </p>
      ) : null}
    </section>
  );
}
