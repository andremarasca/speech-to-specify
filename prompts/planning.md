# Planning Prompt Template

You are a technical architect specialized in breaking down specifications into executable plans.

## Context

You have:
1. A Constitution defining principles and constraints
2. A Specification defining what to build

## Your Task

Create a Planning document that defines:

1. **Technical Approach**: High-level architecture decisions
2. **Task Breakdown**: Ordered list of implementation tasks
3. **Dependencies**: What blocks what
4. **Risks**: What could go wrong

## Inputs

### Original Chaotic Text
---
{{ input_content }}
---

### Constitution
---
{{ constitution_content }}
---

### Specification
---
{{ specification_content }}
---

## Output Format

Produce a well-structured Markdown document:

```markdown
# Implementation Plan

## Technical Approach

### Architecture
[High-level architecture description]

### Key Decisions
- Decision 1: [choice] because [rationale]
- Decision 2: [choice] because [rationale]

## Task Breakdown

### Phase 1: Foundation
- [ ] T001: [Task description]
- [ ] T002: [Task description]

### Phase 2: Core Implementation
- [ ] T003: [Task description]
- [ ] T004: [Task description]

### Phase 3: Integration
- [ ] T005: [Task description]

## Dependencies

```
T001 → T002 → T003
         ↘ T004 → T005
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk 1] | [High/Medium/Low] | [Mitigation strategy] |
```

## Rules

1. Tasks must be atomic and independently testable
2. Each task should be completable in < 2 hours
3. Dependencies must be explicit
4. Align with Constitution constraints
5. Cover all Specification requirements

Generate the Implementation Plan now.
