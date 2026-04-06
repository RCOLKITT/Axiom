import { SiteHeader } from "@/components/site-header"
import { HeroSection } from "@/components/hero-section"
import { CoreInsight } from "@/components/core-insight"
import { SpecPreview } from "@/components/spec-preview"
import { ProblemSection } from "@/components/problem-section"
import { FeaturesSection } from "@/components/features-section"
import { ComparisonSection } from "@/components/comparison-section"
import { CTASection } from "@/components/cta-section"
import { SiteFooter } from "@/components/site-footer"

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <SiteHeader />
      <main>
        <HeroSection />
        <CoreInsight />
        <SpecPreview />
        <ProblemSection />
        <FeaturesSection />
        <ComparisonSection />
        <CTASection />
      </main>
      <SiteFooter />
    </div>
  )
}
