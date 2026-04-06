export function CoreInsight() {
  return (
    <section className="relative border-y border-border bg-card/50 py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mx-auto max-w-4xl text-center">
          <p className="mb-4 text-sm font-medium uppercase tracking-wider text-accent">
            The Core Insight
          </p>
          <blockquote className="text-2xl font-semibold leading-relaxed md:text-3xl lg:text-4xl">
            <span className="text-foreground">&ldquo;Code is a compiled artifact.</span>
            <br />
            <span className="text-accent">Specifications are the source code.&rdquo;</span>
          </blockquote>
          <p className="mx-auto mt-8 max-w-2xl text-muted-foreground">
            If LLMs can reliably generate code from specs, then maintaining code is unnecessary. 
            You maintain the spec. Code is regenerated on demand, verified against the spec&apos;s 
            assertions, and cached until the spec changes.
          </p>
        </div>
      </div>
    </section>
  )
}
