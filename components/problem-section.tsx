const problems = [
  {
    stat: "$1.14T",
    label: "Annual cost of software maintenance",
    description: "More than the cost of building new software",
  },
  {
    stat: "60%+",
    label: "Engineering time on maintenance",
    description: "Most headcount maintains, not creates",
  },
  {
    stat: "Weeks",
    label: "Until documentation drifts",
    description: "Specs become stale artifacts fast",
  },
  {
    stat: "Months",
    label: "To onboard new engineers",
    description: "Archaeological code reading required",
  },
]

export function ProblemSection() {
  return (
    <section className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mb-16 text-center">
          <p className="mb-4 text-sm font-medium uppercase tracking-wider text-accent">
            The Problem
          </p>
          <h2 className="text-3xl font-bold md:text-4xl">
            Code is the source of truth.
            <br />
            <span className="text-muted-foreground">Everything else drifts.</span>
          </h2>
        </div>

        <div className="mx-auto grid max-w-4xl gap-px overflow-hidden rounded-lg border border-border bg-border md:grid-cols-2 lg:grid-cols-4">
          {problems.map((problem) => (
            <div
              key={problem.label}
              className="flex flex-col bg-card p-6"
            >
              <span className="text-3xl font-bold text-foreground">
                {problem.stat}
              </span>
              <span className="mt-2 text-sm font-medium text-foreground">
                {problem.label}
              </span>
              <span className="mt-1 text-sm text-muted-foreground">
                {problem.description}
              </span>
            </div>
          ))}
        </div>

        <div className="mx-auto mt-12 max-w-3xl">
          <div className="rounded-lg border border-border bg-card/50 p-6 md:p-8">
            <p className="text-center text-muted-foreground">
              Modern software organizations maintain millions of lines of code that no single 
              person understands. LLM-generated code ships faster but is understood by nobody — 
              doubling the maintenance surface with half the comprehension.
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}
