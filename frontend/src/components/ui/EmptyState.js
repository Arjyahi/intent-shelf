"use client";

export default function EmptyState({
  actionLabel,
  copy,
  onAction,
  title,
}) {
  return (
    <div className="empty-state">
      <h3 className="empty-state__title">{title}</h3>
      <p className="empty-state__copy">{copy}</p>
      {actionLabel && onAction ? (
        <button type="button" className="secondary-button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
