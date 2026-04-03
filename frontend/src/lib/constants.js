export const DEFAULT_APP_NAME =
  process.env.NEXT_PUBLIC_APP_NAME || "IntentShelf";

export const DEFAULT_BACKEND_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:18001";

export const DEFAULT_DEMO_USER_ID =
  process.env.NEXT_PUBLIC_DEFAULT_USER_ID ||
  "00000dbacae5abe5e23885899a1fa44253a17956c6d1c3d25f88aa139fdfc657";

export const DEFAULT_RANKING_STRATEGY = "default";
export const FEED_BATCH_SIZE = 30;
export const SEARCH_BATCH_SIZE = 24;
export const SIMILAR_BATCH_SIZE = 8;
export const MAX_SESSION_EVENTS = 24;
export const MAX_SIGNAL_EVENTS = 16;
export const APP_STATE_STORAGE_KEY = "intentshelf.phase11.state";
