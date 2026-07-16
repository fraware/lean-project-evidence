# Toolchain extraction fixture

Provides a committed `.lpe/lean-extraction.json` with `extractor: lean.toolchain`
and `complete: true` so evidence compile can exercise the toolchain honesty path
without a full Lean/Lake install.

Regex-stub behavior is covered by extracting the same tree after removing the JSON.
