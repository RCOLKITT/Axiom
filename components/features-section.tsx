import { 
  FileText, 
  GitBranch, 
  RefreshCw, 
  Shield, 
  Zap, 
  Users 
} from "lucide-react"

const features = [
  {
    icon: FileText,
    title: "Specs, Not Code",
    description:
      "Define behavior in Axiom's spec language — natural language intent paired with typed I/O examples, invariants, and performance bounds.",
  },
  {
    icon: GitBranch,
    title: "Version Specs in Git",
    description:
      "Every change is a spec change. Pull requests review spec diffs. Code diffs don't exist because code is a build artifact.",
  },
  {
    icon: RefreshCw,
    title: "Regenerate on Demand",
    description:
      "Code is regenerated from specs, verified against all assertions, and cached until the spec changes. Migration is trivial.",
  },
  {
    icon: Shield,
    title: "Verified by Default",
    description:
      "Multi-layer verification: syntactic, example-based, property-based, performance, and integration. Ship with confidence.",
  },
  {
    icon: Zap,
    title: "Debug at Spec Level",
    description:
      "When production behavior is wrong, the fix is always a spec change. Surface spec gaps, not code bugs.",
  },
  {
    icon: Users,
    title: "Onboard in Hours",
    description:
      "New engineers read the spec — the complete, human-readable, verified description of system behavior. No legacy code archaeology.",
  },
]

export function FeaturesSection() {
  return (
    <section className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mb-16 text-center">
          <h2 className="text-3xl font-bold md:text-4xl">
            A new paradigm for software development
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
            Axiom inverts the relationship between code and specifications. 
            The result is software that&apos;s easier to understand, maintain, and evolve.
          </p>
        </div>

        <div className="mx-auto grid max-w-5xl gap-8 md:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <div
              key={feature.title}
              className="group rounded-lg border border-border bg-card p-6 transition-colors hover:border-accent/50"
            >
              <div className="mb-4 inline-flex rounded-md border border-border bg-secondary p-2.5">
                <feature.icon className="h-5 w-5 text-accent" />
              </div>
              <h3 className="mb-2 font-semibold">{feature.title}</h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
