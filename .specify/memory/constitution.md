<!-- SYNC IMPACT REPORT
Version change: N/A (initial) → 1.0.0
Modified principles: None (initial ratification)
Added sections:
  - Core Principles (I–V)
  - Technology Standards
  - Development Workflow
  - Governance
Removed sections: None

Templates reviewed:
  ✅ .specify/templates/plan-template.md
      Constitution Check section references gates; aligned with all five principles.
  ✅ .specify/templates/spec-template.md
      Mandatory sections (User Scenarios & Testing, Requirements, Success Criteria)
      align with Principles III (Test-First) and II (Code Quality). No changes needed.
  ✅ .specify/templates/tasks-template.md
      TDD task ordering (tests before implementation) and module-separation path
      conventions (src/models, src/services) align with Principles I and III. No changes needed.
  ✅ .specify/templates/checklist-template.md
      Generic template; no principle-specific references. No changes needed.
  ✅ .specify/templates/agent-file-template.md
      Runtime guidance template; no principle-specific references. No changes needed.

Follow-up TODOs: None — all placeholders resolved.
-->

# Data Loading Constitution

## Core Principles

### I. Module Separation

Every module MUST have exactly one responsibility. Data loading, preprocessing, model
definition, training loop, and evaluation MUST always be separate modules. No module
may combine more than one of these roles.

**Rationale**: Mixed responsibilities make code harder to test, reuse, and reason about.
Isolated modules can be independently tested, swapped, and understood without reading
the whole system.

### II. Code Quality

All code MUST meet staff-level engineering standards:

- Abstractions MUST be clear and purposeful — no leaky abstractions, no
  organizational-only modules.
- Variable names MUST be descriptive (`close_prices` not `cp`, `hidden_size` not `hs`).
- Functions MUST be short and do one thing. If a function requires a comment to explain
  what it does, it MUST be split or renamed.
- No magic numbers — all constants MUST be named.
- No duplication — repeated logic MUST be extracted into a shared abstraction.
- Explicit over clever: readable code beats concise code.

**Post-task review is mandatory**: After completing any task, review the generated code
for clarity, correctness, and simplicity — then improve it before marking the task done.

### III. Test-First (NON-NEGOTIABLE)

Test-Driven Development is MANDATORY:

1. Write tests.
2. Obtain user approval.
3. Verify tests FAIL.
4. Implement until tests pass.
5. Refactor.

The Red-Green-Refactor cycle MUST be strictly enforced. No implementation code may be
written before a failing test exists for it.

### IV. Incremental Development

All changes MUST be made in the smallest testable chunks possible. Each increment MUST
be independently verifiable before proceeding to the next.

- When requirements are unclear or ambiguous, STOP and ask. Do not make assumptions.
- Do not proceed until answers are received.
- Avoid over-engineering: only implement what is directly requested or clearly necessary.
- Do not add features, refactors, or improvements beyond the scope of the current task.
- Do not design for hypothetical future requirements.

### V. Git Workflow

- Every new project MUST initialize a local git repository before any code is written.
- Every proposed change MUST live on a new branch — never commit directly to `main`
  while work is in progress.
- Changes MUST NOT be merged to `main` until the user explicitly approves them.
- Branch names MUST describe the work they contain.

## Technology Standards

**Language**: Python 3.x

**Core Libraries**:
- `pandas` and `numpy` for data manipulation and numerical operations.
- `pytest` for all tests (unit, integration, contract).

**Module Conventions**:
- Source code lives under `src/`.
- Tests live under `tests/`, organized by type: `tests/unit/`, `tests/integration/`.
- Each source file contains exactly one responsibility (see Principle I).

**Code Style**:
- Follow PEP 8.
- Maximum line length: 100 characters.
- All public functions MUST have type annotations.
- Docstrings only where the interface is non-obvious; never restate the code in prose.

## Development Workflow

**Branch Strategy**:
- `main`: stable, approved code only.
- Feature branches: one branch per proposed change, named descriptively.
- Force-pushes to `main` are prohibited.

**Review Gates (before merging to `main`)**:
1. All tests pass.
2. Generated code reviewed for clarity and correctness (post-task review — see Principle II).
3. Explicit user approval received.

**Complexity Justification**:
- Any deviation from single-responsibility modules MUST be documented with an explicit
  rationale in the plan's Complexity Tracking table.
- Complexity MUST be justified by current need, not anticipated future need.

## Governance

This constitution supersedes all other practices and conventions in the repository.
Conflicts between this constitution and any other document MUST be resolved in favor
of the constitution.

**Amendment Procedure**:
1. Propose the amendment with a clear rationale.
2. Obtain explicit user approval.
3. Update this document and increment the version per the Versioning Policy below.
4. Propagate changes to all dependent templates and documents per the Sync Impact Report.

**Versioning Policy**:
- MAJOR: Backward-incompatible governance changes — principle removals or redefinitions
  that invalidate prior design decisions.
- MINOR: New principle or section added, or materially expanded guidance.
- PATCH: Clarifications, wording improvements, typo fixes, non-semantic refinements.

**Compliance Review**:
- All feature plans (`plan.md`) MUST include a Constitution Check section that gates
  implementation on compliance with these principles.
- All PRs MUST be verified for constitution compliance before merge.

**Version**: 1.0.0 | **Ratified**: 2026-02-26 | **Last Amended**: 2026-02-26
