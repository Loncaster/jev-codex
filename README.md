# Jev for Codex

[![Jev for Codex — 23% fewer execution tokens in a 22-task holdout](assets/jev-codex-social-preview.jpg)](docs/benchmark.md)

Route each Codex subagent to the lightest reliable model and reasoning effort, then fall back safely when Jev cannot make a confident choice. The same plugin adds deterministic code review and recoverable checkpoints to Codex Desktop.

> **About 23% fewer total execution tokens in a 22-task holdout**, compared with `gpt-5.6-sol/medium`, with 22/22 exact-quality passes in both arms. This is a workload-scoped result, not a universal guarantee. [Read the benchmark method and limitations.](docs/benchmark.md)

This is an independent community project. It is not an official project of, or endorsed by, Dario Fontanel, TypeSafe AI, or OpenAI.

## Features

| Feature | Behavior |
|---|---|
| Subagent policy | Requires useful delegation for non-trivial, independently delegable work while keeping coordination and final verification in the parent. |
| Model and effort routing | Discovers models available in the current Codex app and evaluates the newest two numeric GPT families. |
| Conservative Astra use | Selects current-family Astra only for deep work when Jev reports that current-family Sol is insufficient. |
| Safe fallback | Uses `route=inherit` when the key is missing, the Jev provider is unavailable, discovery fails, or confidence is insufficient. |
| Code review | Evaluates 14 typed checks and applies local deterministic policy to produce `BLOCK`, `SECURITY REVIEW`, `NITS`, or `MERGE`. |
| Checkpoints | Validates a nine-section handoff, rejects likely secrets, confines it to the workspace, and writes atomically. |

## Quick start

Run these commands from the fork's root using the Codex CLI that shares the Desktop app's Codex home:

```powershell
codex plugin marketplace add .
codex plugin add jev-codex@jev-codex
```

Configure one of the providers below, quit Codex Desktop completely, relaunch it, and open a new chat. If Desktop asks for hook approval, review the installed `jev-codex` hooks in Settings and trust them to enable automatic routing and checkpoint reminders.

No key yet? The plugin still works: routing returns `route=inherit` and Codex uses the current model.

## Requirements

- Codex Desktop with plugin hooks and subagents.
- Python 3.10 or newer available to Codex.
- Git for review and installation workflows.
- A RouterAI or TypeSafe System One API key for Jev decisions. Routing inherits the current Codex model when no key is available.

## Configure the Jev provider

| Provider | `JEV_API_URL` | `JEV_MODEL` default | Credential variable |
|---|---|---|---|
| RouterAI | `https://routerai.ru/api/v1/decisions` | `~typesafe/jev-latest` | `JEV_API_KEY` |
| TypeSafe | Unset or `https://api.typesafe.ai/v1/systemone` | `jev-latest` | `TYPESAFE_API_KEY` |

Set `JEV_MODEL` to override the model for the selected endpoint. To switch back to the TypeSafe defaults, remove `JEV_API_URL` and `JEV_MODEL`. Each endpoint uses its own credential. Routing inherits the current model and review returns `UNAVAILABLE` if the configured endpoint is unsupported or its credential is missing. This configuration applies to Jev requests for routing and review. Codex continues to use the model and account selected in Desktop. See the [RouterAI Decisions API guide](https://routerai.ru/docs/guides/overview/decisions/overview).

Set the key to its value alone, without a `Bearer ` prefix. Keep keys out of prompts, repositories, checkpoints, issues, and logs.

### Windows Desktop — recommended

1. Quit Codex Desktop completely.
2. Open the Start menu and search for **Edit environment variables for your account**.
3. Under **User variables**, select **New**.
4. For RouterAI, add `JEV_API_URL` and `JEV_MODEL` with the values above, then add `JEV_API_KEY` with the RouterAI key. For TypeSafe, add `TYPESAFE_API_KEY` with the TypeSafe key.
5. Confirm every dialog.
6. Start Codex Desktop again and open a new chat.

You can confirm that the user variable exists without displaying the key:

```powershell
[bool][Environment]::GetEnvironmentVariable("JEV_API_KEY", "User")
```

Expect `True`. For TypeSafe, check `TYPESAFE_API_KEY` instead.

### macOS or Linux

When launching Codex from a terminal, export the provider settings before starting Codex from that same shell. For RouterAI, configure `JEV_API_KEY` in the launcher environment and export these public settings:

```bash
export JEV_API_URL='https://routerai.ru/api/v1/decisions'
export JEV_MODEL='~typesafe/jev-latest'
```

For a launcher-started Desktop app, configure the variable in the environment used by that launcher or login session. Quit and reopen Codex after changing it, then start a new chat.

### Verify routing without exposing the key

In the new chat, ask Codex to route a small subtask with Jev and report only `route`, `reason`, `model`, and `reasoning_effort`. Do not ask it to print the environment variable. A selected model/effort confirms that Jev can use the key; `route=inherit` with `reason=api_key_missing` means the restarted Codex process did not receive it. Other `inherit` reasons are documented in [routing fallbacks](docs/routing.md#fallbacks).

## How routing behaves

The first successful prompt in a chat injects the delegation policy. Before every `spawn_agent`, Codex routes the exact subtask independently. A `route=inherit` result still permits the required subagent; Codex simply omits explicit model and effort overrides.

The router discovers visible general-purpose models and their supported reasoning efforts from a short-lived local `codex app-server --stdio` process. It considers the newest two numeric GPT families present at that time, so it does not depend on hard-coded current-version names. It excludes `ultra` and prefers the lowest-cost pair judged reliable. See [subagent policy](docs/subagents.md) and [routing policy](docs/routing.md).

## Benchmark result

The release policy was selected on 22 calibration tasks, then evaluated on 22 different, frozen repository-analysis tasks. The holdout compared calibrated live Jev routing with `gpt-5.6-sol/medium` across 44 independently recorded executions.

| Metric | Control | Calibrated Jev | Result |
|---|---:|---:|---:|
| Exact quality | 22/22 | 22/22 | Equal in the holdout |
| Total execution tokens | 2,353,254 | 1,645,344 | 30.1% lower aggregate |
| Paired geometric change | — | — | **23.0% fewer** |
| Paired bootstrap 95% interval | — | — | 12.4% to 32.9% fewer |

Uncached input did not show a supported reduction, so the public claim is limited to total Codex execution tokens. See [the full benchmark note](docs/benchmark.md) and [machine-readable summary](benchmarks/holdout-2026-09-30.json).

To opt out of both mandatory delegation and Jev routing:

```powershell
$env:JEV_ROUTER_DISABLED = "1"
```

The opt-out is checked before first-prompt activation. Removing it during the same chat lets a later prompt activate the plugin.

## Code review and checkpoints

Ask Codex to review a diff with Jev or use the installed `jev-review` skill. Empty diffs return `NO_DIFF` and unavailable analysis returns `UNAVAILABLE`. RouterAI reviews report token usage and leave `cost_usd` unset (`null`). Check RouterAI for actual charges.

For long work, the `jev-checkpoint` skill maintains `.codex/jev-checkpoints/<session-id>.md`. Checkpoints are local, ignored by Git, bounded during recovery, and must never contain credentials.

## Privacy

The configured Jev provider receives the subtask description and five typed questions for routing, or the diff, title, description, changed-file list, and fourteen typed questions for review. Model discovery and checkpoint handling stay local. See [security and data flow](docs/security.md).

## Update

Update your local fork checkout, then reinstall the plugin from its marketplace:

```powershell
git pull --ff-only
codex plugin remove jev-codex@jev-codex
codex plugin add jev-codex@jev-codex
```

To bring new upstream changes into the fork, add the original repository as `upstream` once per clone, then fetch and merge:

```powershell
git remote add upstream https://github.com/SomebooksIT/jev-codex.git
git fetch upstream
git merge upstream/main
```

Run the tests, reinstall, and open a new chat after updating.

## Remove

```powershell
codex plugin remove jev-codex@jev-codex
codex plugin marketplace remove jev-codex
```

## Troubleshooting

- `route=inherit`, `api_key_missing`: check the matching provider key under [Configure the Jev provider](#configure-the-jev-provider), restart Codex Desktop, and start a new chat.
- `invalid_provider_config`: set `JEV_API_URL` to one of the two supported HTTPS endpoints.
- `route=inherit`, `model_discovery_failed`: confirm the installed Codex app exposes `codex app-server --stdio`; inheritance remains safe.
- No policy in an existing chat: open a new chat after installation or update.
- Selected model rejected by Codex: the policy retries that subtask once by inheritance without another Jev call.
- Review returns `UNAVAILABLE`: check the key, connectivity, input size, and whether the diff contains secret-like data.

## Development

```powershell
py -3.12 -m unittest discover -s tests -v
py -3.12 "$env:USERPROFILE\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py" ".\plugins\jev-codex"
```

Runtime code uses only the Python standard library. Contribution and security guidance lives in [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Maintenance

This repository is maintained by `SomebooksIT` as an independent community plugin. Compatibility depends on the installed Codex plugin and App Server interfaces; releases are tested on Windows and Ubuntu with Python 3.10 and 3.12. See the [changelog](CHANGELOG.md) for release history.

## Credits

Jev for Codex is inspired by Dario Fontanel's [jev-claude-code](https://github.com/DarioFontanel/jev-claude-code). Dario Fontanel is the author of that upstream work, not the author or maintainer of this Codex plugin. This project is not endorsed by Dario Fontanel or TypeSafe AI. See [NOTICE.md](NOTICE.md).

## License

MIT. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
