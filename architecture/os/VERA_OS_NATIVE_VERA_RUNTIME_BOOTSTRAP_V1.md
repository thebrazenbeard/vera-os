# Vera Mono canonical composition root in the VeraOS resident host

Exact source basis: Vera Mono staged commit
e5af8cb740267bb5674864571e915842bf5e6677.
The Linux resident previously checked that QualifiedVeraRuntime existed
and imported vera_core but never constructed the source-bound canonical
runtime. Its status was therefore a component import rather than runtime
composition evidence.

This revision calls VeraStateDirectory with a single durable path
<resident-state>/vera-state, project identity veraos, base identity
VERA, and then calls QualifiedVeraRuntime.from_state_directory.
Successful construction occurs before the independent Pre-Active SQLite
Store, and the resulting object is retained until the resident exits.
An exception prevents a healthy resident socket and dashboard marker:
there is no fallback that declares a false runtime.

The status has two distinct fields: canonical_runtime_open=true
reflects in-process construction; canonical_runtime_qualified remains
false until independent runtime and behavioral qualification. The
protected_effect_authority field remains false; no trusted external
execution transport, verifier, control-plane operation, or cognition
provider is admitted by this change.

The existing QEMU guest test must demonstrate normal PID1 startup,
VERAOS_RESIDENT_COMPONENTS_COMPOSED_V1, readable local dashboard,
and repeat boot on the same disk, with the native state directory
existing. This is distinct from native physical installation and
an admitted actual model. In particular, local Ollama observed on the
Windows host is NOT reachable by the no-NIC QEMU image and must never
cause cognition_route_qualified=true by discovery alone.
