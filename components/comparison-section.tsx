import { X, Check } from "lucide-react"

const comparisons = [
  {
    category: "Code Assistants",
    examples: "Copilot, Cursor",
    description: "AI-assisted code completion within code-as-source paradigm",
    limitation: "Smarter editing of an artifact Axiom eliminates",
  },
  {
    category: "Coding Agents",
    examples: "Devin, Codegen agents",
    description: "Autonomous agents that write code",
    limitation: "Agents produce code nobody understands",
  },
  {
    category: "App Generators",
    examples: "v0, Replit Agent",
    description: "Generate apps from prompts",
    limitation: "One-shot generation without verification or maintenance story",
  },
  {
    category: "Formal Methods",
    examples: "TLA+, Dafny, Alloy",
    description: "Formal specification languages",
    limitation: "Require PhD-level expertise; no LLM-powered code generation",
  },
]

export function ComparisonSection() {
  return (
    <section className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mb-16 text-center">
          <p className="mb-4 text-sm font-medium uppercase tracking-wider text-accent">
            How We&apos;re Different
          </p>
          <h2 className="text-3xl font-bold md:text-4xl">
            Not AI-assisted coding.
            <br />
            <span className="text-muted-foreground">A fundamental inversion.</span>
          </h2>
        </div>

        <div className="mx-auto max-w-4xl">
          <div className="overflow-hidden rounded-lg border border-border">
            <div className="grid grid-cols-[1fr,1fr,auto] gap-px bg-border text-sm font-medium md:grid-cols-[1fr,1fr,2fr,auto]">
              <div className="bg-secondary p-4">Category</div>
              <div className="hidden bg-secondary p-4 md:block">Examples</div>
              <div className="bg-secondary p-4">Approach</div>
              <div className="bg-secondary p-4 text-center">Axiom</div>
            </div>
            {comparisons.map((row) => (
              <div
                key={row.category}
                className="grid grid-cols-[1fr,1fr,auto] gap-px bg-border text-sm md:grid-cols-[1fr,1fr,2fr,auto]"
              >
                <div className="bg-card p-4">
                  <span className="font-medium">{row.category}</span>
                  <span className="block text-muted-foreground md:hidden">
                    {row.examples}
                  </span>
                </div>
                <div className="hidden bg-card p-4 text-muted-foreground md:block">
                  {row.examples}
                </div>
                <div className="bg-card p-4 text-muted-foreground">
                  {row.limitation}
                </div>
                <div className="flex items-center justify-center bg-card p-4">
                  <Check className="h-5 w-5 text-accent" />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-lg border border-accent/30 bg-accent/5 p-6">
            <div className="flex items-start gap-4">
              <div className="rounded-full bg-accent/20 p-2">
                <Check className="h-5 w-5 text-accent" />
              </div>
              <div>
                <p className="font-medium">Axiom replaces the paradigm, not assists within it.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  Specs everybody understands → Code machines generate → Verification that guarantees correctness
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
