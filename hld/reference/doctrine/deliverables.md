<!-- Distilled from the owner's visual-communication preferences, snapshot 2026-08-30. -->

# Deliverables — visual by default, low-fidelity until asked

- The wireframe deliverable is a **walkable HTML file** (`.hld/WIREFRAMES/index.html`),
  openable in any browser: real layout, hierarchy, navigation, controls, content
  regions, and the important states. Never ASCII-by-default; never silently escalated
  into a polished visual design — low-fidelity is the point until the client asks for
  more.
- Include responsive variants when responsive behavior is central to the decision;
  annotate only where a note clarifies behavior or a constraint.
- Multiple alternatives when the client is choosing between meaningfully different
  layouts — side by side in one file, comparable without switching views.
- Use a diagram instead of a wireframe when the subject is architecture or flow, not
  spatial layout.
- Never claim a visual exists unless it was actually written and opens. If the render
  path is unavailable, say so and record `COULD-NOT-RUN` — do not fall back to ASCII
  silently.
- Reports (UX-REPORT, HANDOFF) are markdown with real tables and evidence links —
  every screenshot referenced by its exact `H4-*` name, every claim with its grade.
