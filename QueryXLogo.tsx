import { useId } from 'react';

export type QueryXLogoProps = {
  /** Icon size. Use 24 for compact navigation and 32–40 for a product header. */
  size?: number | string;
  /** Render the QueryX wordmark next to the icon. */
  showWordmark?: boolean;
  /** Accessible name announced by screen readers. */
  title?: string;
  className?: string;
};

/**
 * QueryX logo
 *
 * The Q is drawn as a geometric lens: its tail becomes the magnifier handle,
 * while the center node hints at a data point / query result.
 */
export function QueryXLogo({
  size = 32,
  showWordmark = true,
  title = 'QueryX',
  className,
}: QueryXLogoProps) {
  const rawId = useId();
  // React useId contains colons; removing them keeps the ids friendly to SVG/CSS tooling.
  const instanceId = rawId.replace(/:/g, '');
  const gradientId = `queryx-gradient-${instanceId}`;
  const titleId = `queryx-title-${instanceId}`;
  const iconSize = typeof size === 'number' ? `${size}px` : size;

  return (
    <span
      className={className}
      role="img"
      aria-label={title}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.55em',
        color: '#0F172A',
        lineHeight: 1,
        whiteSpace: 'nowrap',
      }}
    >
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-labelledby={titleId}
        focusable="false"
        shapeRendering="geometricPrecision"
      >
        <title id={titleId}>{title}</title>
        <defs>
          <linearGradient
            id={gradientId}
            x1="4"
            y1="4"
            x2="21"
            y2="21"
            gradientUnits="userSpaceOnUse"
          >
            <stop offset="0" stopColor="#4F46E5" />
            <stop offset="1" stopColor="#3B82F6" />
          </linearGradient>
        </defs>

        {/* The round Q body doubles as a magnifying lens. */}
        <circle
          cx="10.5"
          cy="10.5"
          r="7.25"
          stroke={`url(#${gradientId})`}
          strokeWidth="3.1"
        />
        {/* Q tail → a short, unmistakable magnifier handle. */}
        <path
          d="M15.65 15.65L20.85 20.85"
          stroke={`url(#${gradientId})`}
          strokeWidth="3.1"
          strokeLinecap="round"
        />
        {/* A single data node keeps the mark legible at 24 × 24. */}
        <circle cx="10.5" cy="10.5" r="1.35" fill={`url(#${gradientId})`} />
      </svg>

      {showWordmark && (
        <span
          aria-hidden="true"
          style={{
            fontFamily:
              'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
            fontSize: '1.05em',
            fontWeight: 650,
            letterSpacing: '-0.035em',
          }}
        >
          Query<span style={{ color: '#4F46E5' }}>X</span>
        </span>
      )}
    </span>
  );
}

export default QueryXLogo;
