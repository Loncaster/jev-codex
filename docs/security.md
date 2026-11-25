# Security and privacy

## External data

The plugin sends HTTPS requests to `https://api.typesafe.ai/v1/systemone` by default. Setting `JEV_API_URL` to `https://routerai.ru/api/v1/decisions` selects RouterAI. The client accepts these two endpoints and rejects HTTP redirects.

- Routing sends the subtask text, detected current/previous family names, selected Jev model identifier, and five typed questions.
- Review sends the diff, title, description, changed-file list, selected Jev model identifier, and fourteen typed questions.

The Authorization header uses `TYPESAFE_API_KEY` for TypeSafe and `JEV_API_KEY` for RouterAI. The plugin does not intentionally log the key, task, diff, request body, or response body.

## Local-only data

Model discovery, supported-effort discovery, policy evaluation, Git diff acquisition, checkpoint validation, checkpoint storage, and compact recovery remain local. The model-discovery child process receives an environment with `JEV_API_KEY` and `TYPESAFE_API_KEY` removed.

## Limits and guards

- Routing rejects task text over 20,000 characters.
- Review rejects external-analysis input over 250,000 characters.
- Jev requests use a five-second timeout and retry HTTP 429 or 529 once.
- The local sensitive-input guard rejects private-key headers, AWS access-key patterns, and credential assignments or bearer headers with non-placeholder values of at least eight characters.
- Checkpoints require nine sections and reject secret-like content before writing.

These checks reduce accidental disclosure; they are not a complete secret scanner. Review the data before invoking external analysis. Do not put credentials in prompts, task files, diffs, checkpoints, issues, or test fixtures.

## Failure behavior

Routing failures inherit the parent model. Review failures return `UNAVAILABLE`, never `MERGE`. Hook failures return empty output. Checkpoint validation fails before replacement and preserves the previous valid checkpoint when replacement fails.

Report vulnerabilities privately as described in the repository [security policy](../SECURITY.md).
