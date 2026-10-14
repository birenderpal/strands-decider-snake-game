# Git checkpoints

1. Commit after each coherent major change.
2. Use descriptive commit subjects and bodies explaining what changed, why, validation, and limitations.
3. Add an annotated Git tag for each major checkpoint or validated milestone. Never overwrite tags.
4. Preserve a baseline tag before substantial rewrites.
5. Label incomplete checkpoints `checkpoint/...` and record pending or failing checks.
6. Reserve release/version tags for validated milestones.
7. Comment non-obvious decisions and safeguards; keep a short CHANGELOG for major changes.
8. Stage only intended changes. Exclude credentials, runtime state, generated files, and unrelated work.
9. Local commits and tags are authorised. Pushing and publishing require user instructions.

# Keep it simple

Use a plain HTML/CSS/JavaScript frontend and a small Python backend. Strands Decider
chooses every move; never replace a model response with a heuristic or random bot.

# Writing style

1. Use short, direct, professional wording in documentation, UI copy, and comments.
   Avoid promotional language, filler praise, and jargon metaphors.
2. Use Commonwealth spelling, sentence case, and correct grammar. Use contractions
   naturally, with apostrophes.
3. Use numbered lists. Avoid em dashes, en dashes, doubled hyphens in prose, and
   capital letters used only for emphasis.
4. Use clear headings in documentation and descriptive labels in the UI. Explain
   what the reader needs to do, including where to run commands or open addresses.
5. Preserve commands, identifiers, file paths, Markdown syntax, and legal text.
   Keep exact model prompts when editing copy so language changes do not alter
   decisions.
