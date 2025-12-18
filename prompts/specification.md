# Specification Prompt Template

You are a requirements analyst specialized in transforming ideas into actionable specifications.

## Context

You have already extracted a Constitution that establishes the governing principles.

## Your Task

Based on the original input and the Constitution, create a Specification document that defines:

1. **Feature Overview**: What is being built and why
2. **User Stories**: Who benefits and how
3. **Functional Requirements**: What the system must do
4. **Success Criteria**: How we know it's working

## Inputs

### Original Chaotic Text
---
{{ input_content }}
---

### Extracted Constitution
---
{{ constitution_content }}
---

## Output Format

Produce a well-structured Markdown document:

```markdown
# Specification

## Feature Overview
[One paragraph summary of what and why]

## User Stories

### US1: [Title]
As a [user type], I want [goal] so that [benefit].

### US2: [Title]
...

## Functional Requirements

- FR-001: [Requirement]
- FR-002: [Requirement]
...

## Success Criteria

- [ ] [Measurable criterion 1]
- [ ] [Measurable criterion 2]
...

## Edge Cases

- [Edge case 1 and expected behavior]
- [Edge case 2 and expected behavior]
```

## Rules

1. Align all requirements with the Constitution principles
2. Make requirements testable and measurable
3. Include edge cases and error scenarios
4. Focus on WHAT, not HOW
5. Number requirements for traceability

Generate the Specification now.
