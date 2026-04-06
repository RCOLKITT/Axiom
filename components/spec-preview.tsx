"use client"

import { useState } from "react"
import { cn } from "@/lib/utils"

const specCode = `spec: create_user_endpoint
version: 1.2.0

intent: |
  HTTP POST endpoint that creates a new user account.
  Validates input, hashes the password, stores in database,
  and returns the created user without the password field.

interface:
  input:
    type: HTTPRequest
    method: POST
    path: /api/users
    body:
      email: string (valid email format)
      password: string (min 8 chars, at least one number)
      name: string (non-empty, max 100 chars)
  output:
    success:
      status: 201
      body:
        id: string (UUID v4)
        email: string (matches input.email)
        name: string (matches input.name)
        created_at: string (ISO 8601 timestamp)

invariants:
  - "output.body never contains a 'password' field"
  - "password is stored as a bcrypt hash, never plaintext"
  - "response time < 500ms at p99 under 100 concurrent requests"`

const generatedCode = `// Auto-generated from spec: create_user_endpoint v1.2.0
// DO NOT EDIT - Regenerate from spec if changes needed

import { hash } from 'bcrypt';
import { v4 as uuidv4 } from 'uuid';
import { db } from './database';
import { validateEmail, validatePassword } from './validators';

export async function createUser(req: HTTPRequest) {
  const { email, password, name } = req.body;
  
  // Validate input per spec interface
  if (!validateEmail(email)) {
    return { status: 400, body: { error: 'Invalid email format' }};
  }
  if (!validatePassword(password)) {
    return { status: 400, body: { error: 'Password requirements not met' }};
  }
  if (!name || name.length > 100) {
    return { status: 400, body: { error: 'Invalid name' }};
  }

  // Check for existing user
  const existing = await db.users.findByEmail(email);
  if (existing) {
    return { status: 409, body: { error: 'Email already exists' }};
  }

  // Hash password (spec invariant: never store plaintext)
  const hashedPassword = await hash(password, 12);
  
  const user = await db.users.create({
    id: uuidv4(),
    email,
    name,
    password: hashedPassword,
    created_at: new Date().toISOString()
  });

  // Return without password (spec invariant)
  return {
    status: 201,
    body: { id: user.id, email: user.email, name: user.name, created_at: user.created_at }
  };
}`

export function SpecPreview() {
  const [activeTab, setActiveTab] = useState<"spec" | "code">("spec")

  return (
    <section className="py-20 md:py-28">
      <div className="container mx-auto px-4 md:px-6">
        <div className="mx-auto max-w-5xl">
          <div className="mb-12 text-center">
            <h2 className="text-3xl font-bold md:text-4xl">
              See it in action
            </h2>
            <p className="mt-4 text-muted-foreground">
              Write the spec once. Code is generated, verified, and cached automatically.
            </p>
          </div>

          {/* Code preview window */}
          <div className="overflow-hidden rounded-lg border border-border bg-card shadow-2xl">
            {/* Tab bar */}
            <div className="flex items-center gap-1 border-b border-border bg-secondary/50 px-4">
              <button
                onClick={() => setActiveTab("spec")}
                className={cn(
                  "relative px-4 py-3 text-sm font-medium transition-colors",
                  activeTab === "spec"
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                create_user.axiom
                {activeTab === "spec" && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />
                )}
              </button>
              <button
                onClick={() => setActiveTab("code")}
                className={cn(
                  "relative px-4 py-3 text-sm font-medium transition-colors",
                  activeTab === "code"
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                create_user.ts
                <span className="ml-2 rounded bg-accent/20 px-1.5 py-0.5 text-xs text-accent">
                  generated
                </span>
                {activeTab === "code" && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />
                )}
              </button>
            </div>

            {/* Code content */}
            <div className="overflow-auto">
              <pre className="p-6 text-sm leading-relaxed">
                <code className="font-mono text-muted-foreground">
                  {activeTab === "spec" ? specCode : generatedCode}
                </code>
              </pre>
            </div>
          </div>

          {/* Arrow indicator */}
          <div className="mt-8 flex items-center justify-center gap-4 text-sm text-muted-foreground">
            <span className="rounded-full border border-border bg-card px-4 py-2">
              Write the spec
            </span>
            <svg className="h-6 w-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <span className="rounded-full border border-border bg-card px-4 py-2">
              Code regenerates
            </span>
            <svg className="h-6 w-6 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
            </svg>
            <span className="rounded-full border border-border bg-card px-4 py-2">
              Verified & deployed
            </span>
          </div>
        </div>
      </div>
    </section>
  )
}
