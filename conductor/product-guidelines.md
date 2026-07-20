# Product Guidelines: Antigravity CLI GitHub Action

## 1. Voice and Tone
- **Objective & Constructive**: Feedback must be objective, factual, and strictly focused on the code. Avoid subjective opinions unless they directly impact performance, readability, or standards.
- **Encouraging & Actionable**: Frame issues as opportunities for improvement. Instead of "This code is bad," use "Consider refactoring this to improve readability and performance."
- **Clear & Concise**: Keep review comments short and direct. Developers have limited time; get straight to the point with minimal conversational filler.
- **Humble**: Present the AI's suggestions as helpful peer feedback, not absolute directives (e.g., "Consider...", "A potential improvement could be...").

## 2. Feedback Presentation & UX
- **GitHub Suggested Changes**: Whenever proposing code replacements, always format them using GitHub's native ` ```suggestion ` block. This allows developers to apply the fix with a single click directly from the PR interface.
- **Markdown Enrichment**: Use standard Markdown (bolding key terms, using bullet points, and formatting file paths or variables in code blocks) to make comments highly scannable.
- **Visual Gating & Icons**: Use recognizable icons/emojis strategically to convey severity or category (e.g., 🔒 for security concerns, ⚡ for performance suggestions, 🎨 for style guidelines).
- **Collapsible Long Output**: For detailed explanations or stack traces, wrap the supplementary content in a `<details>` block so it does not clutter the Pull Request feed.

## 3. Pull Request Etiquette
- **Strict Diff Focus**: Do not comment on lines outside the pull request diff unless they have a direct compilation or runtime dependency on the changed lines.
- **De-duplication**: Group similar style or pattern violations into a single, consolidated comment or summary report rather than flooding the PR with identical warnings.

## 4. Security, Privacy, & Logging
- **Log Sanitation**: Mask any API keys, credentials, or private configuration values in action execution logs.
- **Least Privilege**: Only request the minimum GitHub token scopes (`contents: read`, `pull-requests: write`) required to read the code and write inline comments.
