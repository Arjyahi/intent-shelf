"use client";

function Icon({ name }) {
  switch (name) {
    case "bag":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 8h12l1 12H5L6 8Z" />
          <path d="M9 9V7a3 3 0 1 1 6 0v2" />
        </svg>
      );
    case "bookmark":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 4h10v16l-5-3-5 3V4Z" />
        </svg>
      );
    case "close":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m6 6 12 12" />
          <path d="M18 6 6 18" />
        </svg>
      );
    case "heart":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m12 20-6.2-6.1a4.7 4.7 0 0 1 6.6-6.7L12 7.6l-.4-.4a4.7 4.7 0 0 1 6.6 6.7L12 20Z" />
        </svg>
      );
    case "minus":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M5 12h14" />
        </svg>
      );
    case "plus":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </svg>
      );
    case "search":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      );
    case "sun":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2.5" />
          <path d="M12 19.5V22" />
          <path d="m4.9 4.9 1.8 1.8" />
          <path d="m17.3 17.3 1.8 1.8" />
          <path d="M2 12h2.5" />
          <path d="M19.5 12H22" />
          <path d="m4.9 19.1 1.8-1.8" />
          <path d="m17.3 6.7 1.8-1.8" />
        </svg>
      );
    case "moon":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M20.4 14.5A8.5 8.5 0 1 1 9.5 3.6a7 7 0 1 0 10.9 10.9Z" />
        </svg>
      );
    case "sliders":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M4 6h16" />
          <path d="M4 12h16" />
          <path d="M4 18h16" />
          <circle cx="8" cy="6" r="2" />
          <circle cx="15" cy="12" r="2" />
          <circle cx="11" cy="18" r="2" />
        </svg>
      );
    case "sparkles":
      return (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="m12 3 1.2 3.8L17 8l-3.8 1.2L12 13l-1.2-3.8L7 8l3.8-1.2L12 3Z" />
          <path d="m18 14 .7 2.1 2.1.7-2.1.7L18 20l-.7-2.1-2.1-.7 2.1-.7L18 14Z" />
          <path d="m6 15 .8 2.2L9 18l-2.2.8L6 21l-.8-2.2L3 18l2.2-.8L6 15Z" />
        </svg>
      );
    default:
      return null;
  }
}

export function Glyph({ name, className = "" }) {
  return (
    <span className={`icon-glyph ${className}`.trim()}>
      <Icon name={name} />
    </span>
  );
}

export default function IconButton({
  active = false,
  className = "",
  icon,
  label,
  variant = "default",
  ...props
}) {
  const classes = [
    "icon-button",
    variant === "primary" ? "icon-button--primary" : "",
    variant === "compact" ? "icon-button--compact" : "",
    active ? "is-active" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button type="button" className={classes} {...props}>
      {icon ? <Glyph name={icon} /> : null}
      {label ? <span>{label}</span> : null}
    </button>
  );
}
