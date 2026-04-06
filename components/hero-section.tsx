"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight, Github } from "lucide-react"

export function HeroSection() {
  return (
    <section className="relative py-24 md:py-32 lg:py-40">
      {/* Subtle grid background */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,rgb(255_255_255/0.02)_1px,transparent_1px),linear-gradient(to_bottom,rgb(255_255_255/0.02)_1px,transparent_1px)] bg-[size:64px_64px]" />
      
      <div className="container relative mx-auto px-4 md:px-6">
        <div className="mx-auto max-w-4xl text-center">
          {/* Eyebrow */}
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-secondary/50 px-4 py-1.5 text-sm text-muted-foreground">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
            </span>
            Now in private beta
          </div>
          
          {/* Main headline */}
          <h1 className="text-balance text-4xl font-bold tracking-tight md:text-5xl lg:text-6xl">
            Write specs, not code.
            <br />
            <span className="text-muted-foreground">
              Let machines do the rest.
            </span>
          </h1>
          
          {/* Subheadline */}
          <p className="mx-auto mt-6 max-w-2xl text-balance text-lg text-muted-foreground md:text-xl">
            Axiom is a development platform where humans write executable specifications 
            and machines generate, verify, and maintain the code.
          </p>
          
          {/* CTA buttons */}
          <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Button size="lg" className="h-12 px-8 text-base">
              Get Early Access
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button variant="outline" size="lg" className="h-12 px-8 text-base">
              <Github className="mr-2 h-4 w-4" />
              Star on GitHub
            </Button>
          </div>
          
          {/* Social proof hint */}
          <p className="mt-8 text-sm text-muted-foreground">
            Join 2,400+ engineers rethinking how software is built.
          </p>
        </div>
      </div>
    </section>
  )
}
