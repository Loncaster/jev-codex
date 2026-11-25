# Model and effort routing

The router minimizes expected compute while retaining conservative quality gates. It makes one fresh decision per subtask and never changes the parent chat model.

## Discovery

`jev_route.py` runs `app-server --stdio` using the executable in `CODEX_APP_RUNTIME_CLI_PATH` when available, with `codex` from `PATH` as the fallback. It requests `model/list` after initialization. The process has a three-second discovery timeout and receives an environment with both Jev provider keys removed.

The catalog verifies the configured model IDs and their supported efforts. Hidden and specialty entries are excluded. If GPT-6.2 Sol is unavailable or the catalog cannot be read completely, routing inherits the parent configuration.

## Jev decision

Jev evaluates four typed values:

- least sufficient tier: `fast`, `balanced`, or `deep`;
- least sufficient reasoning effort;
- probability that an underpowered model would cause material harm;
- probability that GPT-6 Luna at `low` is insufficient for a fast task.

Tier confidence below `0.30` inherits. Fast routing and downgrades below a known parent tier require at least `0.60`. When the current parent model is unknown, only a `deep` decision can select an explicit model.

## Model and effort pairs

| Tier | Model | Effort |
|---|---|---|
| `fast` | GPT-6 Luna when sufficient, with GPT-6.1 Terra as the stronger lightweight option | `low` |
| `balanced` | GPT-6.2 Sol | `medium` |
| `deep` | GPT-6.2 Sol | `high`, `xhigh`, or `max` |

Fast routing requires risk at most `0.30`. Luna is eligible when its insufficiency probability is at most `0.50`. When no suitable lightweight model supports `low`, the router uses GPT-6.2 Sol at `medium`. Risk above `0.70` promotes the task to `deep`.

For deep work, Jev's score selects an effort of at least `high`. If the requested Sol effort is unavailable, the router tries a supported higher effort through `max` before inheriting.

## Fallbacks

The router returns `route=inherit` without `model` or `reasoning_effort` when:

- the configured Jev provider's API key is missing or `JEV_API_URL` is unsupported;
- `JEV_ROUTER_DISABLED=1`;
- the task contains secret-like input or exceeds 20,000 characters;
- App Server discovery fails or produces an incomplete catalog;
- the Jev provider times out, rejects the request, or returns invalid data;
- confidence or parent-model safety rules reject an explicit downgrade;
- no compatible model/effort pair exists.

Inheritance is successful safe behavior. It does not cancel useful delegation. When Codex rejects an explicit pair, the policy retries once by inheritance without another Jev request.
