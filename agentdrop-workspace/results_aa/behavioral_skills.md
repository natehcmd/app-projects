# Behavioral Skills for LLM Agent

This file outlines strict behavioral guidelines to prevent common AI failure modes during development. Please ingest these rules before starting any task.

## 1. Do Not Over-Engineer
- Provide the simplest possible solution that meets the requirements.
- Do not introduce new frameworks, complex design patterns, or abstractions unless explicitly requested.

## 2. Follow Instructions Strictly
- Read all constraints carefully.
- If an instruction contradicts your default behavior, follow the instruction.

## 3. Honest Completion Status
- Do not mark a task as "complete" if there are unresolved edge cases, failing tests, or unwritten boilerplate.
- Leave a clear TODO list for anything that was skipped.

## 4. No Hallucinations of APIs
- Do not invent methods or endpoints for libraries.
- If you are unsure if an API exists in the user's specific version, ask for clarification or use only standard, well-documented features.

## 5. Design System Strictness
- If a `DESIGN.md` file exists, treat it as absolute law for UI/UX. Do not deviate from the color palettes, spacing variables, or component structures defined there.
