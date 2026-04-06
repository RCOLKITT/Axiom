export function AxiomLogo({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 120 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Logomark - Abstract "A" formed by converging lines representing spec → code transformation */}
      <g>
        {/* Left diagonal */}
        <path
          d="M4 28L16 4"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Right diagonal */}
        <path
          d="M28 28L16 4"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Horizontal bar - represents the "axiom" / foundational truth */}
        <path
          d="M8 20H24"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        {/* Small accent dot at apex - the "source" */}
        <circle cx="16" cy="4" r="2" fill="currentColor" className="text-accent" />
      </g>
      
      {/* Wordmark */}
      <text
        x="38"
        y="23"
        fill="currentColor"
        fontFamily="var(--font-sans)"
        fontSize="20"
        fontWeight="600"
        letterSpacing="-0.02em"
      >
        axiom
      </text>
    </svg>
  )
}

export function AxiomMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Left diagonal */}
      <path
        d="M4 28L16 4"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Right diagonal */}
      <path
        d="M28 28L16 4"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Horizontal bar */}
      <path
        d="M8 20H24"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* Accent dot at apex */}
      <circle cx="16" cy="4" r="2" fill="currentColor" className="text-accent" />
    </svg>
  )
}
