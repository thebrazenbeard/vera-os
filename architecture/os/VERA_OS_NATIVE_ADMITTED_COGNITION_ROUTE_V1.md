# VeraOS native admitted local cognition path V1

## Status and evidence
Source candidate only, based on actual pinned staged packages:
Portal 7d00d8bf3b48c0676b2278359838ee563c66c67f,
Pre-Active 1f23a809d7274df506e03e2d9052525538c3bcf6,
Vera Mono e5af8cb740267bb5674864571e915842bf5e6677.

The new native_cognition module uses VeraOS cognition-provider descriptor
validation, the existing Pre-Active ModelTarget local-loopback check,
a live /v1/models exact-model probe, actual P.O.R.T.A.L. typed route
advertisement and resolve_portal_route, Pre-Active Engine,
ContextAssembler, and ToolRegistry with NO registered effect tools.
The Pre-Active Store durably records events, runs and model outputs.
Bounded input sizes, stable request tokens, deduplication, no remote
API kinds, no nonloopback targets and no protected-effect authorizations
are enforced. A stored model result is reported as completed only when
the Pre-Active run is actually COMPLETED.

## Proof
TDD: initial new source tests failed as expected. In the full local
unit/integration suite a controlled loopback OpenAI-compatible HTTP
test service was used. Its GET /models and POST /chat/completions were
actually invoked. The P.O.R.T.A.L. binding selected a single eligible
cognition-only route; the real Pre-Active Store persisted a run with a
text model result; replaying the same request made no second HTTP call.
HELD and REMOTE_API providers, mismatched endpoints, absent model IDs,
prohibited effect claims, oversized requests, nonloopback SSRF target,
and reused request id for a different task fail closed.

The fake local HTTP server used by the tests is not a real cognitive
model and cannot qualify production behavior. The test provider record
contains illustrative qualification digest strings, not externally
attested VeraOS qualification evidence. No real model qualification
is issued by this source candidate.

## Deliberate unactivated limits
The actual VeraOS guest still has no NIC or admitted provider; host
Ollama inventory cannot imply guest reachability, policy admission,
or model response quality. No route is installed/registered into the
default resident startup and the GUI remains no-cognition until a
separately validated exact provider/admission binding is installed.
The manual admission function requires callers to authenticate the
provenance of provider records; its schema validation is NOT a proof
that the record issuer really qualified the model. No arbitrary
host/guest port relay is enabled by this change.

Canonical Vera runtime is separate from the local model and remains
the sole identity/governance owner. No protected tools, identity
writes, network egress, production model route, physical OS install,
or main merge are granted here.

Next: independently review the route/admission proof boundary and
integrate a locally confined transport + explicit verified model
qualification into the guest, then qualify guest invocation and
UI conversation through the resident IPC.
