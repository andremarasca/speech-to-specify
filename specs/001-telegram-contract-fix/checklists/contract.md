# Contract Checklist: Telegram Contract Fix

**Purpose**: Validate requirement quality for Telegram interface contract mapping (commands, callbacks, keyboards, recovery/search flows).
**Created**: 2025-12-19
**Feature**: [specs/001-telegram-contract-fix/spec.md](specs/001-telegram-contract-fix/spec.md)

## Requirement Completeness
- [x] CHK001 Are all documented commands (/start, /status, /done, /finish, /transcripts, /search, /session, /help, /preferences, /process, aliases) explicitly mapped to handlers with expected responses defined? [Completeness, Spec §FR-001, Tasks §Phase 3]
- [x] CHK002 Are all inline callback prefixes (action/help/recover/confirm/nav/retry/page/search) enumerated with handler expectations and no orphaned callbacks? [Completeness, Spec §FR-002, Tasks §T015]
- [x] CHK003 Are recovery flows for INTERRUPTED/orphan sessions fully specified (prompting, resume, finalize, discard) including required messages and state updates? [Completeness, Spec §FR-007, Tasks §T027-T028]
- [x] CHK004 Is the conversational search state (awaiting query) and pagination TODO documented with interim safe behavior? [Completeness, Spec §FR-010, Research §4]
- [x] CHK005 Are help topics and fallback behaviors cataloged for all states and UIService outage cases? [Completeness, Spec §FR-008, Tasks §T029]
- [x] CHK006 Are UIPreferences (simplified vs normal) requirements documented for commands, keyboards, and persistence points? [Completeness, Spec §FR-009, DataModel §PreferenciasUI]

## Requirement Clarity
- [x] CHK007 Are “acknowledge-only” callbacks (close_help, dismiss, page:current) defined with explicit user feedback/logging expectations? [Clarity, Spec §FR-003, DataModel §CallbackAction]
- [x] CHK008 Is the message for unknown/unsupported commands specified with wording and allowed suggestions (e.g., /help)? [Clarity, Edge Case, Spec §Edge Cases]
- [x] CHK009 Are search result pagination behaviors (page numbering, invalid page input) described with concrete responses and state retention rules? [Clarity, Spec §FR-010]
- [x] CHK010 Are performance targets for command/callback responses stated per scenario class (p95 ≤800ms light, ≤2s with storage) and how they are measured? [Clarity, Research §1]

## Requirement Consistency
- [x] CHK011 Do command aliases (/done=/finish, /transcripts vs /process) share consistent messaging and keyboards across spec, plan, and tasks? [Consistency, Spec §FR-001, Plan §Summary, Tasks §Phase 3]
- [x] CHK012 Are callback routing rules aligned between keyboards definitions and daemon handlers (no prefix drift)? [Consistency, Spec §FR-002, Tasks §T015, Tasks §T023]
- [x] CHK013 Are configuration values (SEARCH_TIMEOUT, PAGINATION_PAGE_SIZE, HELP_FALLBACK_ENABLED, ORPHAN_RECOVERY_PROMPT) consistently externalized across requirements and quickstart? [Consistency, Spec §FR-012, Research §2, Quickstart §2]

## Acceptance Criteria Quality
- [x] CHK014 Are success metrics (SC-001..SC-006) mapped to measurable acceptance tests with clear data/steps (e.g., interaction counts, p95 thresholds)? [Acceptance Criteria, Spec §Success Criteria]
- [x] CHK015 Are blocking test gates defined (pytest suites) and tied to requirement IDs to ensure coverage enforcement? [Acceptance Criteria, Spec §FR-013, Quickstart §4, Tasks §T005-T018]

## Scenario Coverage
- [x] CHK016 Are primary flows (start→status→done, search→select, recovery prompts) covered with requirements for all expected states and transitions? [Coverage, Spec §User Story 1-3]
- [x] CHK017 Are alternate flows for conversational search (no inline query, awaiting query) specified with prompts and exits? [Coverage, Spec §FR-004, Research §4]
- [x] CHK018 Are exception flows for backend/search timeout, missing sessions, or invalid payloads specified with user-facing responses and logging? [Coverage, Spec §Edge Cases, Spec §FR-010, Spec §FR-011]

## Edge Case Coverage
- [x] CHK019 Are behaviors for invalid callbacks (e.g., page:abc, stale search callbacks after restart) defined with state preservation rules? [Edge Case, Spec §Edge Cases, Tasks §T022, Tasks §T037]
- [x] CHK020 Is the case of recovering a non-existent or already handled orphan session documented with required UI cleanup? [Edge Case, Spec §Edge Cases]
- [x] CHK021 Are zero-result search responses and retry/return options specified? [Edge Case, Spec §Edge Cases, Spec §FR-004]

## Non-Functional Requirements
- [x] CHK022 Are logging/observability fields and levels mandated for invalid callbacks, search failures, and recovery paths? [Non-Functional, Spec §FR-011, Research §5, Tasks §T033]
- [x] CHK023 Are external configuration requirements explicit for all operational values with prohibition of hardcoding and auditability expectations? [Non-Functional, Spec §FR-012, Tasks §T036, Quickstart §2]
- [x] CHK024 Are concurrency/pagination state assumptions for single-instance bot documented and bounded? [Non-Functional, Research §3, Research §4]

## Dependencies & Assumptions
- [x] CHK025 Are dependencies on session storage, UIService availability, and search backend availability explicitly stated with fallbacks? [Dependencies, Spec §FR-004, Spec §FR-008, Research §4]
- [x] CHK026 Are assumptions about chat-level state tracking (in-memory awaiting_search_query) documented with cleanup/expiry rules? [Assumption, Research §4, DataModel §UIState]

## Ambiguities & Conflicts
- [x] CHK027 Are any undefined command names or keyboard labels flagged for clarification before implementation? [Ambiguity, Gap]
- [x] CHK028 Are conflicting expectations between performance targets (Research §1, Spec §SC-003, Spec §SC-004) reconciled? [Conflict, Research §1, Spec §SC-003, Spec §SC-004]
- [x] CHK029 Is a traceability scheme linking FR/SC to tests documented to avoid orphan requirements? [Traceability, Spec §FR-013, Tasks §T005-T018]
