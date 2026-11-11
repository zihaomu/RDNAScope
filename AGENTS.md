# RDNAScope

Read `docs/roadmap.md` and `docs/implementation.md`. Record each completed step
and actual validation in the implementation log. The original prototype and
FreeToken inputs are read-only; do not relocate them or rewrite their evidence.

Default analysis is CPU/offline only. Explicit command jobs do not qualify GPU support.
GPU collection and device qualification require
their own explicit task and the parent workspace environment/resource rules.
No GPU support, calibrated clocks or model performance qualification follows
from software tests or from a successful query.

Use `.venv/bin/python -m pytest -q` after functional changes. Verify wheel
installation outside the checkout when changing packaging/resources. Keep
models, traces, machine profiles, caches and private experiment data out of Git.
GC defaults to preview. Validate destructive/timeout cases on synthetic fixtures;
do not clean real caches outside the user's explicit cleanup scope. External evidence
and unmanaged legacy files are never lifecycle GC targets.
Do not commit/push or modify a user's accepted model baseline without scope.
