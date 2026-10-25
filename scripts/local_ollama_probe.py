"""Read-only local inference qualification; not a VeraOS install or model identity proof.

The only destination is numeric IPv4 loopback. The caller must pin the exact
Ollama *manifest* digest; a friendly name such as vera-local is not a pin.
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import re
import sys

_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_MODEL = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
    r"(?:/[A-Za-z0-9][A-Za-z0-9_.-]{0,63})?"
    r"(?::[A-Za-z0-9][A-Za-z0-9_.-]{0,63})?\Z"
)
_MAX_RESPONSE = 131_072
_SCHEMA = "VERA_OS_OLLAMA_SOURCE_PROBE_V1"


class ProbeError(Exception):
    """No qualified response; preserve the fail-closed result."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("ambiguous JSON object")
        result[name] = value
    return result


def _decode_json(raw: bytes) -> object:
    def reject_nonfinite(_: str) -> None:
        raise ValueError("nonfinite JSON number")

    def parse_finite_float(value: str) -> float:
        decoded = float(value)
        if not math.isfinite(decoded):
            raise ValueError("nonfinite JSON number")
        return decoded

    return json.loads(
        raw.decode("utf-8"), object_pairs_hook=_unique_object,
        parse_constant=reject_nonfinite, parse_float=parse_finite_float,
    )


def _request_json(port: int, method: str, path: str,
                  body: dict[str, object] | None) -> object:
    """One fixed-path request without redirects, credentials or proxy use."""
    payload = None if body is None else json.dumps(body, separators=(",", ":")).encode()
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10.0)
    try:
        connection.request(
            method, path, body=payload,
            headers={"Content-Type": "application/json", "Connection": "close"},
        )
        response = connection.getresponse()
        if response.status != 200:
            raise ProbeError("local Ollama HTTP status is not 200")
        declared = response.getheader("Content-Length")
        if declared is not None and (
            not declared.isdecimal() or int(declared) > _MAX_RESPONSE
        ):
            raise ProbeError("invalid local Ollama response length")
        raw = response.read(_MAX_RESPONSE + 1)
        if len(raw) > _MAX_RESPONSE:
            raise ProbeError("local Ollama response exceeds read budget")
        try:
            return _decode_json(raw)
        except (UnicodeError, ValueError) as error:
            raise ProbeError("invalid local Ollama JSON") from error
    finally:
        connection.close()


def qualify(model: str, manifest_digest: str, port: int = 11434,
            *, generate: bool = False, request_json=None) -> dict[str, object]:
    """Verify exact served manifest then optionally execute a bounded prompt.

    The result never claims that the manifest is a Vera-tuned adapter, a
    governed runtime, or a durable identity. The caller supplies the pin.
    """
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("port must be a numeric TCP port")
    if type(model) is not str or not _MODEL.fullmatch(model):
        raise ValueError("exact model name required")
    if type(manifest_digest) is not str or not _HEX64.fullmatch(manifest_digest):
        raise ValueError("exact 64-hex Ollama manifest digest required")
    if type(generate) is not bool:
        raise ValueError("generate must be Boolean")

    result: dict[str, object] = {
        "schema": _SCHEMA,
        "status": "HOLD",
        "endpoint": f"127.0.0.1:{port}",
        "model": model,
        "expected_manifest_digest": manifest_digest,
        "manifest_digest_verified": False,
        "bounded_generation_verified": False,
        "vera_runtime_verified": False,
        "vera_adapter_verified": False,
        "activation_authorized": False,
    }
    call = request_json or _request_json
    try:
        listing = call(port, "GET", "/api/tags", None)
        if type(listing) is not dict or type(listing.get("models")) is not list:
            return result
        matches = [entry for entry in listing["models"]
                   if type(entry) is dict and entry.get("name") == model]
        if len(matches) != 1 or matches[0].get("digest") != manifest_digest:
            return result
        result["manifest_digest_verified"] = True
        if generate:
            generated = call(port, "POST", "/api/generate", {
                "model": model, "prompt": "Reply with the word READY.",
                "stream": False, "options": {"num_predict": 24},
            })
            if (type(generated) is not dict
                    or generated.get("model") != model
                    or generated.get("done") is not True
                    or type(generated.get("response")) is not str
                    or not generated["response"].strip()):
                return result
            result["bounded_generation_verified"] = True
        result["status"] = "MANIFEST_AND_GENERATION" if generate else "MANIFEST_ONLY"
    except (OSError, TimeoutError, http.client.HTTPException, ProbeError, ValueError):
        return result
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--manifest-digest", required=True)
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument("--generate", action="store_true",
                        help="ask the pinned model a fixed, bounded smoke prompt")
    args = parser.parse_args(argv)
    try:
        outcome = qualify(args.model, args.manifest_digest, args.port,
                          generate=args.generate)
    except ValueError:
        outcome = {"schema": _SCHEMA, "status": "HOLD",
                   "error": "invalid_probe_configuration",
                   "activation_authorized": False}
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome.get("status") in {
        "MANIFEST_ONLY", "MANIFEST_AND_GENERATION",
    } else 1


if __name__ == "__main__":
    sys.exit(main())
