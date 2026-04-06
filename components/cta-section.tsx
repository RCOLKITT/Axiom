"use client"

import { Button } from "@/components/ui/button"
import { ArrowRight, Mail } from "lucide-react"
import { useState } from "react"

export function CTASection() {
  const [email, setEmail] = useState("")
  const [submitted, setSubmitted] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (email) {
      setSubmitted(true)
    }
  }

  return (
    <section className="border-t border-border py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold md:text-4xl">
            Ready to stop maintaining code?
          </h2>
          <p className="mt-4 text-muted-foreground">
            Join the private beta and be among the first to experience 
            the future of software development.
          </p>

          {!submitted ? (
            <form onSubmit={handleSubmit} className="mt-8">
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
                <div className="relative flex-1 sm:max-w-sm">
                  <Mail className="absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="h-12 w-full rounded-lg border border-border bg-input pl-10 pr-4 text-foreground placeholder:text-muted-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    required
                  />
                </div>
                <Button type="submit" size="lg" className="h-12 px-8">
                  Get Early Access
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </form>
          ) : (
            <div className="mt-8 rounded-lg border border-accent/30 bg-accent/10 p-6">
              <p className="font-medium text-accent">You&apos;re on the list!</p>
              <p className="mt-1 text-sm text-muted-foreground">
                We&apos;ll reach out soon with your beta access.
              </p>
            </div>
          )}

          <p className="mt-6 text-xs text-muted-foreground">
            No spam. Unsubscribe anytime. We&apos;ll only email you about Axiom.
          </p>
        </div>
      </div>
    </section>
  )
}
