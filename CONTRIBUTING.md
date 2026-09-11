# Contributing

Contributions should preserve Mindseam's selective, lightweight operating design and keep the
English and Chinese README files aligned when shared behavior or public claims change.

Before submitting a change:

1. Keep edits scoped to a demonstrated problem or a clearly stated capability.
2. Reuse established suite language when a script enforces a documented invariant.
3. Run the integrity check and the complete standard-library test suite on Python 3.
4. Add a focused regression test for any controller or verifier defect.
5. Identify the source and rights for any external text, code, data, image, or model trace. Do
   not submit unauthenticated leaked material.
6. Drive the controller through `tests/_controller_helper.invoke_cli` rather than spawning a
   fresh interpreter. A real spawn costs roughly 400 ms, almost all of it Python startup and
   the module import, while the controller does about 30 ms of work — the suite was spending
   ~99% of its wall time waiting on children. Keep subprocess only where the child boundary
   *is* the thing under test (the encoding, root-state, and stdin-pipe guards do this), and add
   the module to `SPAWNING_ALLOWLIST` in `tests/test_r191_in_process_invocation.py` when you do.

Unless explicitly stated otherwise, intentionally submitted contributions are provided under
the repository's Apache License 2.0 in accordance with Section 5 of that license. Third-party
materials retain their original terms and must also be recorded in `THIRD_PARTY_NOTICES.md`.
