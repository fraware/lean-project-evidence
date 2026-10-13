# Verified execution across changing trust boundaries
## Decision-controlled execution plan, v1.0

**Issued:** 2026-10-13  
**Program horizon:** 2026-10-13 to 2027-12-31  
**Status:** Planning baseline. Evidence-backed local XMSS candidate; upstream and formal-refinement gates open.  
**Primary working repository:** `fraware/lean-project-evidence` (research records only).  
**Upstream implementation owners:** `leanEthereum/leanSpec`, `leanEthereum/leanVM`; future target subject to confirmation.

## 1. Immutable objective and exit criteria

**Mission.** Develop mathematical foundations, software mechanisms, and evaluation methods that allow security-critical systems to execute, evolve, and compose while preserving independently checkable guarantees.

Success requires **all** four outcomes:

1. An accepted, reviewed, security-relevant contribution to a maintained Ethereum implementation.
2. A substantial Lean 4 theorem connecting real implementation semantics to a formal specification, with explicit trusted assumptions, no unresolved admitted dependencies in its claimed result, and independent reproduction.
3. A single meaningful compositional or evidence-applicability mechanism, applied in **two independently maintained systems** without altering its core formal meaning.
4. A scientific result specifying the precise guarantee, boundary cases, comparison with existing methods, and independently checkable evaluation data.

These are **targets**, never presumed outcomes. An abstract safety theorem is not a concrete implementation refinement. A GitHub Actions green run is not upstream acceptance. A counterexample-free finite evaluation is not a universal proof.

## 2. Evidence baseline and current external dependencies

| Reference | Exact evidence / current observation | Meaning |
|---|---|---|
| XMSS latest combined candidate | `fraware/lean-project-evidence@79b27bba5154298de32681dcadcc8ec8628de54b` | Atomic slot reservation, validator preconditions, persistence classification, bounded recovery and adversarial tests. |
| Acceptance CI | [Run #38464729618](https://github.com/fraware/lean-project-evidence/actions/runs/38464729618), **success**, 76 focused, 2,971 full-suite passed, 91.79% measured coverage; Ruff formatting/lint and `ty` succeeded | Tests run against pinned upstream PR #1204 revision; default test tree explicitly excludes interoperability suites. |
| Upstream signing PR | [leanSpec #1204](https://github.com/leanEthereum/leanSpec/pull/1204), head `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`; open, unmerged, merge state `dirty` | Requires maintainer coordination and integration rebase. |
| Original security issue | [leanSpec #1203](https://github.com/leanEthereum/leanSpec/issues/1203), open | Broader stateful-XMSS signing concern; issue is not automatically closed by passing tests. |
| Upstream Rust/Aeneas proof | [leanVM #533](https://github.com/leanEthereum/leanVM/pull/533), head `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`, open draft | The file `verification/leanxmss/LeanxmssProofs/Encoding.lean` contained admitted `fold6`, `fold12`, `encode_spec` at inspected revision. |
| Alternative circuit paths | [leanVM #595](https://github.com/leanEthereum/leanVM/pull/595) and [#610](https://github.com/leanEthereum/leanVM/pull/610), open | Competing/possibly complementary verification architectures; do not choose without a deployment-relevance assessment. |
| Upstream permissions | No direct write permission to `leanEthereum/leanSpec`. `fraware/leanSpec` fork absent at last check | Reviewer handoff may proceed now; publishing to upstream needs correctly authorized contribution route. |
| Reviewer reconstruction | [Handoff branch](https://github.com/fraware/lean-project-evidence/tree/research/ethereum-xmss-durability-handoff-20261013/handoff_xmss_durability) | Six SHA-pinned candidate files and local diff-generation script; execute independently before treating as verified handoff. |

### Non-negotiable distinction

- **Already established:** reproducible bounded failure scenarios, a passing six-file composed candidate, an abstract Lean reservation safety model with 9 proved theorems under its assumptions, and a 512-transition conformance experiment.
- **Not established:** independent upstream adoption, hardware crash durability, backup anti-rollback, universal Python/SQLite refinement, safe independent operation of cloned key material, a completed Rust-guest equivalence proof, or system-wide zkVM security.

## 3. Execution principles

**One critical path at a time.** Engineering and proof work proceed in two concurrent lanes, not equal efforts on four repos. No new general platform before a useful, checked concrete theorem.

**No unsafe claims.** A change is GREEN only if the exact commit's relevant full CI completed successfully. A theorem is COMPLETE only after its own statement, axioms, generated dependencies, toolchain, and trust semantics are examined. A contribution is UPSTREAM only after the upstream repo records it as accepted/merged.

**Prefer minimum diff.** Start with a regression test and narrow correction aligned to maintainer scope. Avoid silently changing signing policy, consensus behavior, or deployed claims.

**Preserve operational differences.** Process restart, OS crash, storage power loss, file-backup rollback, and independent key copies are distinct adversary capabilities. Production fail-closed policy is an explicit decision, not an incidental side effect.

**Do not fabricate external action.** Handoff prepared is distinct from comment posted; candidate tested is distinct from maintainer review.

## 4. Workstreams, dependencies, and measurable gates

### A. XMSS upstream integration (P0, target: October 13–November 15)

| ID | Work package | Concrete work and artifact | Acceptance / dependency |
|---|---|---|---|
| A0 | Freeze current evidence | Record exact source and candidate SHAs, workflow logs, 76/2,971 counts, trust boundaries, and all changed file hashes in a single claims ledger | Every positive claim traces to an exact checked source/CI run |
| A1 | Independent candidate reconstruction | Execute `handoff_xmss_durability/review_candidate.sh` in a clean environment, compare SHA list, generate diff, and inspect for unintended API changes | Patch reconstructs byte-identically; `git diff --check` clean |
| A2 | Expand test surface | Explicitly run upstream interop and fault-injection suites omitted from `pytest tests`, or report precisely why a suite cannot run; use isolated development keys | Results linked to exact upstream and candidate revisions |
| A3 | Validate trust model | Audit key identity / reassignment, process connection concurrency, SQLite journaling settings, backup rollback, key custody, and fail-closed production choice | Threat-model table covers each environment with supported/unsupported status and test evidence |
| A4 | Maintainer-facing change proposal | Prepare a brief, source-linked review for #1204 author `adust09`: exact failing scenarios; minimal atomic monotonic reservation; persistence classification and backup caveat; CI link | Reviewer acknowledges scope or documented response; do not assume availability |
| A5 | Choose integration split | Decide with maintainers whether to amend #1204 (preferred for storage changes), separate signer preconditions into an independent PR, or produce a smaller follow-up | Each contribution has a reviewed target base and explicit API/behavior boundary |
| A6 | Publish correctly | Create/authenticate `fraware/leanSpec` fork if necessary, replay minimal patches, resolve parent PR conflict, open attributable draft/ready PRs; never push to an unauthorized origin | Public upstream review link with checks green on exact PR head |
| A7 | External review and iteration | Address maintainers' comments; add missing negative tests and update proof/model claims; rebase safely if upstream moves | Approved and merged upstream contribution, or documented rejection with bounded fallback |

**Critical dependency:** A4/A5 establish whether A6's implementation target is compatible with the author's accepted deployment model. Do not run a competing PR until that is resolved or clearly time-boxed.

**Security-sensitive handling:** Any newly discovered exploitable real deployment condition beyond the disclosed issue is routed through upstream's stated security disclosure process instead of public exploit publication.

### B. leanVM implementation-equivalence proof (P0/P1, first target: October 13–November 30)

| ID | Work package | Concrete work and artifact | Acceptance / dependency |
|---|---|---|---|
| B0 | Pin competing architectures | Record #533/#595/#610 heads, source/proof dependencies, build and verification entrypoints, and trusted translation/model obligations | Versioned comparison and decision memo |
| B1 | Independent baseline | Recreate #533's Lean environment, run existing checks, obtain `#print axioms` (or equivalent complete dependency report) for `verify_spec` and `verify_ok_iff` | Baseline makes use of `sorryAx` and other trust assumptions explicit; no false claim from build success |
| B2 | Obtain maintainer direction | Ask which path blocks the intended deployment and which interface is stable; present the specific current proof obligations, not a generic collaboration request | Maintainer response or a time-boxed selection with explicit uncertainty |
| B3 | Target first smallest useful lemma | For #533 if still needed, first evaluate feasibility of `fold6`; prove against exact upstream definitions, then `fold12` | Lean kernel checks the exact lemma without admitted assumptions |
| B4 | Discharge `encode_spec` | Establish both successful and rejected-input behavior and each chain digit's correspondence to `wotsEncode`, preserving guest semantics | Checked statement; higher-level theorem's axiom closure audited |
| B5 | Bridge remaining models | Independently examine Aeneas/Charon extraction, closure patches, external SDK shims, manually transcribed guest I/O, actual Rust program revision; address one highest-priority binding gap | Explicit relation to implementation source or documented remaining assumptions |
| B6 | Upstream proof review | Provide minimal theorem patch, runnable reproduction, axiom report, performance, and review notes | Maintainer-reviewed integration decision and CI outcome |

**Decision switch:** If maintainers prioritize Lean-authored circuits (#610/#595), redirect B3–B5 toward source-to-circuit/public-input/verifier binding. An extracted guest proof and a circuit-soundness result are not interchangeable.

**Stop/redirect:** If #533 is inactive, source shifts materially, or a theorem duplicates existing work, time-box the effort and select a maintainer-recognized obligation on #610/#595 or another critical component. Preserve completed lemmas and negative results.

### C. Concrete system semantics (P1, target: December 2026–March 2027)

1. Define one trace model with observable `validate`, `reserve`, `commit`, `sign`, `recover` transitions and explicit crash assumptions.
2. Prove a monotonic-authorization invariant and a non-reuse result for the stated model.
3. State refinement conditions connecting implementation operations and committed durable state to model transitions, with correct treatment of errors and interleavings.
4. Discharge the strongest feasible implementation obligations. Do not substitute a bounded enumerator or proof about a simplified mock for universal refinement.
5. Instantiate the same evidence discipline in leanVM: exact source, circuit identity, bound public inputs, verifier semantics, soundness assumptions, and accepted result.

**Gate C:** At least one property of a real end-to-end boundary established by checked composition plus explicit independently reviewed premises, without conflating safety, liveness, and probabilistic soundness.

### D. Reusable compositional evidence mechanism (P1, target: January–April 2027)

1. Choose a specific preservation claim observed in A/B/C, not a generic claim registry.
2. Define a typed object containing proposition, source/implementation hashes, proof statement, axioms, semantic mapping, explicit assumptions, and relied-on environment.
3. Define machine-checkable authorization rules with three outcomes: `supported`, `incomplete`, `refuted`. Absence of proof is not proof of falsity.
4. Prove a nontrivial preservation theorem across the chosen change/embedding, including trace/public-input alignment and failure conditions; do not hide the desired conclusion inside `Compatible`.
5. Implement the smallest checker and deny unsupported claims by construction. Keep domain adapters outside its trusted core.
6. Test proof mutations: changed proof target, swapped artifact identity, stale verifier, removed premise, divergent domain separation, upgraded semantics, different key identity.
7. Review closely related theorem and evidence frameworks for genuine novelty; abandon a redundant generic platform.

**Gate D:** An independently checked nontrivial preservation theorem and corresponding executable checker that rejects deliberately invalid evidence, with a precise specification of residual trust.

### E. Portability experiment (P2, target: May–August 2027)

- First target: Ethereum signing/verification workflow (actual upstream-useful boundary).
- Second target: independently maintained **different semantic domain**, provisionally external autonomous-execution or scientific control software; a second internally owned demo does not satisfy independence.
- Verify unmodified core theorem and checker semantics in both instantiations. Adapters and external model mappings are separately audited.
- Freeze evaluation protocol before collecting results: matched tasks, reviewer assignment, acceptance definitions, task difficulty stratification, recorded exposure/carryover, comparison baseline using the same Lean tools.
- Primary metrics: unsupported authorization count/denominator; accepted critical-path obligations per reviewer-hour; reproducibility; false escalation rate; reviewer time; maintenance/proof-repair cost.
- Suggested operating targets from the earlier plan for a prospective pilot: 30–50 candidate artifacts, >=80% packet construction, >=90% exact-environment reproduction, <=10% expert-time overhead. These are **targets only**, not observed results.
- Publish all failures and uncertainty. Zero observed false authorizations does not establish zero true failure probability.

**Gate E:** A core mechanism independently reproduced on two separately maintained systems, prospective comparison against a credible baseline, and a defensible interpretation of results.

### F. Consolidation and adoption (P2, target: September–December 2027)

1. Release a fixed versioned evidence pack with exact code, proof environment, axiom/dependency audit, tests, traces, and reproduction scripts.
2. Seek independent Ethereum and external-domain reviews with recorded issues/resolutions.
3. Write a scientific article anchored in proved results, external adoption, and comparative evidence; explicitly distinguish original contributions from prior art.
4. Demonstrate an actual downstream workflow consuming checked evidence instead of trusting an assertion from our tooling.
5. Decide continuation only after external adoption and sustained maintenance are real.

**Gate F:** All four mission exit criteria satisfied; failures or incomplete gates declared without hedging.

## 5. Tactical calendar — first 14 days

| Date (2026) | Work | Daily exit artifact | Dependency / scope |
|---|---|---|---|
| Tue Oct 13 | A0: freeze passing commit and CI. A1: review SHA-verified handoff; file this execution plan. B0: snapshot proof PR heads | Evidence manifest; ready-to-reproduce source handoff; plan | No upstream write |
| Wed Oct 14 | A1: execute clean-room reconstruct. A2: test interop and classify what is truly exercised. B1: prepare exact upstream leanVM proof environment | Reproduction log, test matrix, Lean toolchain manifest | Execute only with pinned revisions |
| Thu Oct 15 | A3: key identity, rollback, SQLite crash model, signer availability/fail-closed decisions. B1: inspect theorem axiom closure | Revised threat model and axiom/dependency report | No inflated durability or proof claims |
| Fri Oct 16 | A4: source-supported #1204 technical review. B2: pointed question about #533 vs #610 deployment path | Prepared/published upstream comments, with explicit publication status | User-authenticated contributor access or maintainer permission |
| Sat–Sun Oct 17–18 | B3: bounded first lemma effort; A5: integration split and source rebase rehearsal | First compiled proof candidate or exact blocker; integration decision memo | No changed trusted model without justification |
| Mon Oct 19 | A6: establish authorized fork and review branch, transfer narrowed patches | PR-ready branch and verified changes | Maintainer response or time-boxed choice |
| Tue Oct 20 | B3: finish/advance selected leaf theorem; rerun relevant Lean checks | Lean proof commit and axiom audit | Stay on exact pinned definitions |
| Wed Oct 21 | A6: open appropriate upstream PR / propose patch to existing author; run upstream-specific CI | Actual upstream link or explicitly blocked state | Prevent competing uncoordinated PR |
| Thu Oct 22 | B4: scope `encode_spec` or #610 artifact binding; construct negative tests | Dependency-accurate proof task and adversarial test | Architecture selection |
| Fri Oct 23 | A7: incorporate reviewer notes and ensure full focused+interop CI. B4: check partial proof | Maintainer feedback and revised proofs | Do not claim merge from review alone |
| Sat–Sun Oct 24–25 | C0/D0: formalize one candidate composition proposition, survey nearest prior art | One-page statement; assumptions; novelty screen | Stay minimal |
| Mon Oct 26 | Recheck both acceptance gates and resolve integration/research blockers | Decision log: accepted, blocked, redirected | Time-box idle upstream dependencies |
| Tue Oct 27 | Sprint close and next-sprint selection based on actual evidence | Versioned gate report and 30-day queue | Explicitly record unsupported claims |

### First 72-hour minimum

- SHA-pinned reproducibility pack for green XMSS candidate.
- Separate standard vs interoperability test results.
- Signed-off technical risk matrix including backup rollback/key custody and configuration diagnostics.
- Exact Lean #533 proof baseline and admitted-dependency analysis.
- Maintainer-facing, source-supported proposals for both workstreams, clearly marked as sent or merely prepared.

## 6. Subsequent stage checkpoints

| Target | What must exist | What does NOT count |
|---|---|---|
| Oct 31, 2026 | Reproducible XMSS integration handoff; maintainers contacted through proper GitHub channels; formal target chosen with documented grounds | Local CI alone as upstream acceptance |
| Nov 15, 2026 | An upstream-reviewed signer change or documented blocker/alternative and demonstrable progress on a real Lean proof | Unreviewed replacement branch |
| Dec 15, 2026 | Checked lemma or bounded equivalence property with complete axiom/dependency report; signed-off trust boundary inventory | Lean build containing unrelated admitted dependencies described as complete equivalence |
| Jan 15, 2027 | Substantial reproducible implementation-correspondence contribution; C model fixed | Abstract proof called end-to-end correctness |
| Apr 30, 2027 | One nontrivial reusable preservation theorem and working fail-closed checker on a real case | File-hash comparison alone |
| Aug 31, 2027 | Independent second deployment and prospective evaluation | Two projects under same operator without independent verification |
| Dec 31, 2027 | Four mission success criteria, external review and replication, scientific report | Draft publication or research prototype without results |

If a critical gate fails, revise scope and dates; never silently waive the gate.

## 7. Roles and external actions

- **Research/engineering operator (our side):** artifact auditing, pinned rebuilds, minimal patches, tests, theorem development, reproduction, evaluation protocol, and claim accounting.
- **User-controlled GitHub credential:** creating/authenticating the fork or publishing comments/PRs where the connected tool is read-only. The necessary intervention is narrow and exact.
- **Upstream maintainer:** selects architecture and integration policy; owns acceptance of protocol/security changes.
- **Independent reviewer:** verifies at least one fully pinned reproduction and reviews specification adequacy / critical assumptions before broader claims.

Do not assume a maintainer has replied; do not count a prepared comment as a published discussion. Continue local proof work while waiting, instead of creating a daily-watch workstream.

## 8. Decision log rules and stop conditions

| Condition | Response |
|---|---|
| #1204 author accepts a narrow durability correction | Supply minimal amendment, tests, and evidence rather than six-file competing PR |
| #1204 author rejects multi-writer scope | Keep atomic-concurrency work as a bounded optional hardening; avoid falsely describing the original supported deployment as exploitable |
| Production safety depends on persistent reservations | Propose an explicit fail-closed option; maintain development/test mode deliberately |
| Upstream PR parent has merge conflicts | Rebase on the exact current upstream base and test again; do not use obsolete green run as evidence for rebased code |
| #533 is on critical path | Target admitted `fold6` then `fold12` and `encode_spec`; separately audit source binding |
| #610/#595 supersede the guest verification path | Redirect to actual circuit/public-input/execution correspondence, not superficial theorem duplication |
| The purported novel composition theorem follows directly from existing literature | Reuse and extend the established result; do not rebrand a standard theorem |
| No maintainer response by next decision point | Continue bounded independent proof, then make a documented target selection with a clear review status |
| Second independent project is unavailable | Search for an external maintained target; do not report internal demos as proof of portability |
| Tests cannot reproduce the claimed environment | Mark the claim incomplete and fix environment documentation before publication |

## 9. Progress ledger

For each work package record: `id`, `owner`, `state` (queued/active/blocked/checked/reviewed/accepted), `source_sha`, `artifact_sha`, `test_or_theorem`, `assumptions`, `limitations`, `external_review_url`, `next_decision`.

Weekly reviews should ask:
1. What new **externally useful** obligation was actually discharged?
2. Which theorem/trace/test establishes that result, at which exact commit?
3. Which trusted assumption or upstream dependency remains the limiting factor?
4. What is the next smallest operation to remove that factor?
5. Did any previously asserted claim lose its evidentiary basis because sources changed?

The project advances on **gates**, not code volume, branch count, or messages sent.

## 10. Next executable actions

**Action 1 — Clean-room XMSS handoff and interop:** run the six-file reconstruction script from the source-pinned handoff branch and the upstream interoperability suite explicitly. Record outputs, environment and failures.

**Action 2 — Publication-ready PR #1204 review:** condense the local reproduced results and evidence, choose one specific change requested from `adust09`, and prepare a minimal diff and supporting tests. Maintain no claim of an actual comment until GitHub confirms publication.

**Action 3 — leanVM exact proof audit:** recreate #533 proof environment; examine each `sorry`, its dependency closure, and whether `fold6` is both feasible and wanted upstream. Record choice between #533 and #610 in a decision memo.

**Action 4 — Research theorem selection:** from those concrete gaps choose a single nontrivial implementation-to-claim preservation obligation; defer platform implementation until a checked theorem and one independent real use exist.

These actions may be conducted in parallel where dependencies permit. No task entails holding an unseen background process; each execution must report results or explicit blockers.
