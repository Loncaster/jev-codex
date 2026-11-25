---
name: jev-review
description: Use when reviewing a diff before a commit, merge, or pull request, or when deciding whether code changes are safe to merge.
---

# Jev Review

Use the plugin's `scripts/jev_review.py` as the source of the verdict. Do not inspect the diff first to invent or replace that verdict.

Run with `--json` and choose exactly one source:

- uncommitted tracked changes: `--working`;
- a Git base reference: `--git <ref>`;
- a `.diff` or `.patch` file: `--diff <path>`.

Pass `--title` and `--description` from the user's request when available. If the script reports `api_key_missing`, explain that RouterAI needs `JEV_API_KEY` and TypeSafe needs `TYPESAFE_API_KEY` in the Desktop process environment. Never ask the user to paste a key into chat.

Report the returned verdict and triggered comparisons unchanged. Then report only noteworthy checks, `primary_concern`, elapsed milliseconds, token usage, and cost when available. Treat `merge_ready` as informational and never as policy.

Inspect code only for checks listed in `escalation`. For each, open the relevant changed file and answer the uncertain question with one concise finding and its supporting line. If escalation is empty, say so and stop the review.

For `NITS`, `SECURITY REVIEW`, or `BLOCK`, ask the user separately before applying any fix. The review itself is read-only. If repeated evidence shows a classification problem, propose a change to `checks.json` criteria, not to thresholds or Python policy code.
