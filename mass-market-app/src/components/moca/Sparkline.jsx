/**
 * Pure presentational SVG sparkline.
 *
 * Takes a numeric array (e.g. price history) and renders a smooth line with
 * a dot at the last point. For the API-fetching variant, see <SparklineMini>.
 *
 * <Sparkline data={[78, 79, 81, 79, 75, 74]} color="#5c3317" />
 * <Sparkline data={[...]} fill w={120} h={28} />
 */
export default function Sparkline({
  data,
  color,
  w = 80,
  h = 22,
  dotted = false,
  fill = false,
  strokeWidth = 1.5,
}) {
  const stroke = color || 'var(--color-moca-bolt)'
  if (!data || data.length < 2) return null

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const step = w / (data.length - 1)
  const pts = data.map((v, i) => [i * step, h - ((v - min) / range) * h])
  const d = pts
    .map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1))
    .join(' ')
  const last = pts[pts.length - 1]

  return (
    <svg
      width={w}
      height={h}
      style={{ display: 'block', overflow: 'visible' }}
      aria-hidden="true"
    >
      {fill && (
        <path
          d={`${d} L${w},${h} L0,${h} Z`}
          fill={stroke}
          fillOpacity="0.08"
        />
      )}
      <path
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={dotted ? '2 2' : '0'}
      />
      <circle cx={last[0]} cy={last[1]} r="2.5" fill={stroke} />
    </svg>
  )
}
