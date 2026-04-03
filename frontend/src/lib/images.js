const FALLBACK_GRADIENTS = [
  "linear-gradient(140deg, #c78f6a, #efd8c9)",
  "linear-gradient(140deg, #9f6b59, #e8d0c0)",
  "linear-gradient(140deg, #7d8f73, #d7e3d3)",
  "linear-gradient(140deg, #8e6b57, #dcc8bc)",
  "linear-gradient(140deg, #8f7a57, #ebe1c9)",
];

function hashValue(value = "") {
  let hash = 0;

  for (const character of value) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }

  return hash;
}

export function getProductImageUrl(imagePath) {
  if (!imagePath) {
    return null;
  }

  return `/api/images?path=${encodeURIComponent(imagePath)}`;
}

export function getProductFallbackGradient(productId) {
  return FALLBACK_GRADIENTS[hashValue(productId) % FALLBACK_GRADIENTS.length];
}
