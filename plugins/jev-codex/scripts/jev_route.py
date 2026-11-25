"""Choose a Codex subagent model for one task, or inherit safely."""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import re
import subprocess
import threading
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from jev_client import JevUnavailable, ask_jev, contains_sensitive_input, jev_request_options


EFFORTS = ("low", "medium", "high", "xhigh", "max")
BASE_MODEL = "gpt-6.2-sol"
TERRA_MODEL = "gpt-6.1-terra"
LUNA_MODEL = "gpt-6-luna"
MODEL_ID = re.compile(r"^gpt-(\d+(?:\.\d+)?)-(luna|terra|sol|astra)$")
TIERS = ("fast", "balanced", "deep")
QUESTIONS = {
    "tier": {
        "type": "choice",
        "instructions": "Choose the least costly Codex tier that can complete this subtask reliably.",
        "criteria": {
            "fast": "A clearly specified, low-risk mechanical lookup, edit, or verification with at most a few routine steps. No design, diagnosis, or judgment.",
            "balanced": "Ordinary implementation, debugging, or review with bounded complexity.",
            "deep": "Architecture, security, migration, ambiguity, or high-consequence reasoning.",
        },
    },
    "effort": {
        "type": "score",
        "instructions": "Score the least reasoning effort that can complete this subtask reliably.",
        "criteria": [
            "Almost none: direct mechanical work.",
            "Some: normal bounded reasoning.",
            "A lot: multi-step or cross-cutting reasoning.",
            "Very high: unusually difficult or adversarial reasoning.",
            "Maximum: the hardest tasks that still do not require automatic delegation.",
        ],
    },
    "risky": {
        "type": "noul",
        "instructions": "Estimate the probability of material harm to data, security, or production if the subtask is done poorly. A wrong answer to a read-only lookup that can be checked easily has negligible risk.",
        "criteria": {
            "false": "Read-only lookup or check, or a low-consequence and readily reversible edit.",
            "true": "Security, data, production, or irreversible consequence.",
        },
    },
    "luna_insufficient": {
        "type": "noul",
        "instructions": "For a fast subtask, estimate whether GPT-6 Luna at low effort would be insufficient.",
        "criteria": {
            "false": "Direct lookup or one obvious check with an explicit input or target.",
            "true": "Still mechanical and low-risk, but requires interpreting several inputs or carrying out a few tightly bounded steps.",
        },
    },
}


def _fallback(reason: str) -> dict[str, object]:
    return {"route": "inherit", "reason": reason}


def _number(value: object, minimum: float = 0, maximum: float = 1) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise ValueError
    return number


def _decision(payload: object) -> tuple[str, float, str, float, float]:
    if not isinstance(payload, dict) or not isinstance(payload.get("answers"), dict):
        raise ValueError
    answers = payload["answers"]
    required = (
        answers.get("tier"),
        answers.get("effort"),
        answers.get("risky"),
        answers.get("luna_insufficient"),
    )
    if not all(isinstance(answer, dict) for answer in required):
        raise ValueError
    tier_answer, effort_answer, risk_answer, luna_answer = required

    tier = tier_answer.get("choice")
    if tier not in TIERS:
        raise ValueError
    confidence = _number(tier_answer.get("confidence"))
    effort_score = _number(effort_answer.get("score"), 0, 4)
    effort_confidence = _number(effort_answer.get("confidence"))
    risk = _number(risk_answer.get("noul"))
    luna_insufficient = _number(luna_answer.get("noul"))
    if risk > 0.7:
        tier = "deep"
    elif tier == "fast" and risk > 0.3:
        tier = "balanced"

    if tier == "deep":
        effort = EFFORTS[max(2, int(effort_score + 0.5))] if effort_confidence >= 0.3 else "high"
    else:
        effort = "low" if tier == "fast" else "medium"
    return tier, confidence, effort, risk, luna_insufficient


def _send(process: object, message: dict[str, object]) -> None:
    process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    process.stdin.flush()


def _receive(process: object, request_id: int) -> dict[str, object]:
    for _ in range(20):
        line = process.stdout.readline()
        if not line:
            raise RuntimeError("app_server_eof")
        message = json.loads(line)
        if not isinstance(message, dict) or message.get("id") != request_id:
            continue
        if "error" in message or not isinstance(message.get("result"), dict):
            raise RuntimeError("app_server_error")
        return message["result"]
    raise RuntimeError("app_server_response_missing")


def discover_models(
    *,
    process_factory: Callable[..., object] = subprocess.Popen,
    timeout: float = 3.0,
) -> list[dict[str, object]]:
    """Read the visible Codex model catalog through one short-lived App Server."""
    child_env = dict(os.environ)
    child_env.pop("TYPESAFE_API_KEY", None)
    child_env.pop("JEV_API_KEY", None)
    options: dict[str, object] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "env": child_env,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    desktop_cli = child_env.get("CODEX_APP_RUNTIME_CLI_PATH")
    executable = desktop_cli if desktop_cli and Path(desktop_cli).is_file() else "codex"
    process = process_factory([executable, "app-server", "--stdio"], **options)
    result: queue.Queue[tuple[bool, object]] = queue.Queue(maxsize=1)

    def transact() -> None:
        try:
            _send(
                process,
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "clientInfo": {"name": "jev-codex", "version": "0.1.6"},
                        "capabilities": {"experimentalApi": True},
                    },
                },
            )
            _receive(process, 1)
            _send(process, {"method": "initialized"})
            _send(
                process,
                {
                    "id": 2,
                    "method": "model/list",
                    "params": {"includeHidden": False, "limit": 100},
                },
            )
            response = _receive(process, 2)
            models = response.get("data")
            if not isinstance(models, list) or response.get("nextCursor") is not None:
                raise RuntimeError("incomplete_model_catalog")
            result.put((True, models))
        except BaseException as exc:
            result.put((False, exc))

    threading.Thread(target=transact, daemon=True).start()
    try:
        try:
            ok, value = result.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("model_discovery_timeout") from exc
        if not ok:
            raise RuntimeError("model_discovery_failed") from value
        return value
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                process.kill()


def _catalog(models: object) -> dict[str, tuple[str, ...]]:
    if not isinstance(models, list):
        raise ValueError
    catalog: dict[str, tuple[str, ...]] = {}
    for item in models:
        if not isinstance(item, dict) or item.get("hidden") is True or item.get("modelSpecialty") is not None:
            continue
        name = item.get("model")
        supported = item.get("supportedReasoningEfforts")
        if name not in (BASE_MODEL, TERRA_MODEL, LUNA_MODEL) or not isinstance(supported, list):
            continue
        efforts = tuple(
            effort
            for effort in EFFORTS
            if any(
                isinstance(option, dict) and option.get("reasoningEffort") == effort
                for option in supported
            )
        )
        if efforts:
            catalog.setdefault(name, efforts)
    if BASE_MODEL not in catalog:
        raise ValueError
    return catalog


def _clamp_effort(requested: str, supported: tuple[str, ...]) -> str:
    index = EFFORTS.index(requested)
    for effort in EFFORTS[index:]:
        if effort in supported:
            return effort
    raise ValueError


def _model_tier(model: str | None) -> str | None:
    if model in (LUNA_MODEL, TERRA_MODEL):
        return "fast"
    match = MODEL_ID.fullmatch(model) if isinstance(model, str) else None
    if match is None:
        return None
    role = match.group(2)
    return "fast" if role == "luna" else "deep" if role == "astra" else "balanced"


def route_task(
    task: str,
    *,
    current_model: str | None,
    env: Mapping[str, str],
    ask: Callable[..., object] = ask_jev,
    discover: Callable[[], object] | None = None,
) -> dict[str, object]:
    if env.get("JEV_ROUTER_DISABLED") == "1":
        return _fallback("disabled")
    try:
        request_options = jev_request_options(env)
    except JevUnavailable as exc:
        return _fallback(exc.reason)
    if contains_sensitive_input(task):
        return _fallback("sensitive_input")
    if len(task) > 20_000:
        return _fallback("input_too_large")

    try:
        catalog = _catalog((discover or discover_models)())
    except Exception:
        return _fallback("model_discovery_failed")

    try:
        tier, confidence, effort, risk, luna_insufficient = _decision(
            ask(
                {"task": task},
                QUESTIONS,
                **request_options,
            )
        )
    except JevUnavailable as exc:
        return _fallback(exc.reason)
    except (KeyError, TypeError, ValueError):
        return _fallback("invalid_response")
    except Exception:
        return _fallback("unexpected_error")

    if confidence < 0.3:
        return _fallback("low_confidence")

    parent_tier = _model_tier(current_model)
    if parent_tier is None:
        if tier != "deep":
            return _fallback("unknown_current_model")
    elif confidence < 0.6 and (tier == "fast" or TIERS.index(tier) < TIERS.index(parent_tier)):
        return _fallback("low_confidence")

    model = BASE_MODEL
    if tier == "fast":
        if luna_insufficient <= 0.5 and "low" in catalog.get(LUNA_MODEL, ()):
            model = LUNA_MODEL
        elif "low" in catalog.get(TERRA_MODEL, ()):
            model = TERRA_MODEL
        else:
            tier, effort = "balanced", "medium"
    try:
        effort = _clamp_effort(effort, catalog[model])
    except ValueError:
        return _fallback("model_discovery_failed")

    return {
        "route": tier,
        "model": model,
        "reasoning_effort": effort,
        "confidence": confidence,
        "risk": risk,
        "luna_insufficient": luna_insufficient,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--current-model")
    args = parser.parse_args(argv)
    try:
        task = Path(args.task_file).read_text(encoding="utf-8")
        result = route_task(
            task,
            current_model=args.current_model or os.environ.get("CODEX_MODEL"),
            env=os.environ,
        )
    except Exception:
        result = _fallback("unexpected_error")
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
