const REASON_TAG_LABELS = {
  anchor_similarity: "Anchor similarity",
  collaborative_signal: "Collaborative support",
  content_signal: "Visual similarity",
  fallback: "Fallback rule",
  multi_signal: "Multiple signals",
  recent_views: "Recent views",
  search_match: "Search match",
  session_signal: "Session signal",
  shopping_intent: "Shopping intent",
};

function formatLabel(value) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function normalizeExplanation(explanation) {
  if (!explanation) {
    return null;
  }

  return {
    shortReason: explanation.short_reason,
    supportingReasons: explanation.supporting_reasons || [],
    reasonTags: explanation.reason_tags || [],
    explanationSource: explanation.explanation_source,
    evidence: explanation.evidence
      ? {
          ruleName: explanation.evidence.rule_name,
          dominantSource: explanation.evidence.dominant_source,
          meaningfulSources: explanation.evidence.meaningful_sources || [],
          contributingSources: explanation.evidence.contributing_sources || [],
          queryPresent: explanation.evidence.query_present,
          queryText: explanation.evidence.query_text,
          normalizedQuery: explanation.evidence.normalized_query,
          sessionContextUsed: explanation.evidence.session_context_used,
          sessionSignalCount: explanation.evidence.session_signal_count,
          sourceCount: explanation.evidence.source_count,
          multiSourceSignal: explanation.evidence.multi_source_signal,
          diversityPenalty: explanation.evidence.diversity_penalty,
        }
      : null,
  };
}

function normalizeProduct(item, source, extra = {}) {
  return {
    id: item.product_id,
    productId: item.product_id,
    productName: item.product_name,
    productTypeName: item.product_type_name || null,
    productGroupName: item.product_group_name || null,
    colourGroupName: item.colour_group_name || null,
    departmentName: item.department_name || null,
    imagePath: item.image_path || null,
    hasImage: Boolean(item.has_image),
    explanation: normalizeExplanation(item.explanation),
    contributingSources: item.contributing_sources || [],
    rankingPosition: item.ranking_position || null,
    searchQuery: extra.searchQuery || null,
    discoverySource: source,
    raw: item,
  };
}

export function normalizeFeedProduct(item) {
  return normalizeProduct(item, "feed");
}

export function normalizeSearchProduct(item, searchQuery) {
  return normalizeProduct(item, "search", {
    searchQuery,
  });
}

export function normalizeSimilarProduct(item) {
  return normalizeProduct(
    {
      ...item,
      contributing_sources: ["content"],
    },
    "similar",
  );
}

export function getProductSubtitle(product) {
  return [product.productTypeName, product.productGroupName]
    .filter(Boolean)
    .join(" / ");
}

export function formatReasonTag(tag) {
  return REASON_TAG_LABELS[tag] || formatLabel(tag);
}

export function formatSourceLabel(source) {
  if (!source) {
    return "Mixed";
  }

  const labels = {
    collaborative: "Collaborative",
    content: "Similar style",
    fallback: "Fallback",
    search: "Search",
    session: "Session",
    similar: "Similar items",
  };

  return labels[source] || formatLabel(source);
}

export function getPrimarySignal(product) {
  if (product.explanation?.explanationSource) {
    return product.explanation.explanationSource;
  }

  if (product.discoverySource === "similar") {
    return "content";
  }

  return product.contributingSources[0] || product.discoverySource;
}

export function getReasonPreview(product) {
  if (product.explanation?.shortReason) {
    return product.explanation.shortReason;
  }

  if (product.searchQuery) {
    return `Matched your search for "${product.searchQuery}"`;
  }

  return "Picked for your discovery feed.";
}

export function buildProductMetadata(product) {
  const entries = [
    ["Product type", product.productTypeName],
    ["Product group", product.productGroupName],
    ["Colour", product.colourGroupName],
    ["Department", product.departmentName],
    ["Primary signal", formatSourceLabel(getPrimarySignal(product))],
    [
      "Supporting sources",
      product.contributingSources.length
        ? product.contributingSources.map(formatSourceLabel).join(", ")
        : null,
    ],
  ];

  return entries
    .filter(([, value]) => value)
    .map(([label, value]) => ({
      label,
      value,
    }));
}

export function mergeProductContext(product, productPool) {
  const match = productPool.find((candidate) => candidate.productId === product.productId);

  if (!match) {
    return product;
  }

  return {
    ...match,
    ...product,
    explanation: product.explanation || match.explanation,
  };
}
