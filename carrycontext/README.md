# CarryContext

Portable context capsules for continuing work across ChatGPT, Claude, Gemini, Codex, and other AI tools.

## Problem

People working across multiple AI tools repeatedly lose project context, decisions, constraints, open questions, and useful outputs. Long chats are also hard to navigate.

## Wedge

CarryContext does **not** try to become another universal AI-memory platform. The first version solves one narrow job:

> Paste a conversation, generate a compact structured context capsule, copy it into the next AI tool, and continue.

## MVP

- Runs entirely in the browser.
- No account.
- No backend.
- No API key.
- Paste any AI conversation or working notes.
- Generate a Markdown capsule containing:
  - project/context summary
  - decisions
  - constraints
  - action items
  - open questions
  - continuity instruction for the next AI
- Copy the capsule with one click.

## Target user

Power users who routinely switch among two or more AI assistants while working on ongoing projects.

## Success signal

The MVP is worth continuing if users repeatedly generate capsules for real multi-session work instead of treating it as a one-time summarizer.

## Files

- `index.html` — product UI
- `styles.css` — visual design
- `app.js` — local capsule-generation logic
- `VALIDATION.md` — initial market evidence and product thesis
