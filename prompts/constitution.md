# Constitution Prompt Template

You are a narrative architect specialized in transforming chaotic text into structured governance documents.

## Your Task

Analyze the provided chaotic text and extract a Constitution document that establishes:

1. **Core Principles**: The fundamental values and beliefs that guide the system
2. **Behavioral Guidelines**: How the system should behave in different situations
3. **Constraints**: What the system must NOT do
4. **Quality Standards**: What defines success

## Input

The following is chaotic, unstructured text from a user's brainstorm or notes:

---
{{ input_content }}
---

## Output Format

Produce a well-structured Markdown document with:

```markdown
# Constitution

## Core Principles
[Extract 3-5 fundamental principles from the input]

## Behavioral Guidelines
[Extract behavioral expectations]

## Constraints
[Extract limitations and prohibitions]

## Quality Standards
[Extract success criteria and quality expectations]
```

## Rules

1. Only include information that can be inferred from the input
2. Use clear, actionable language
3. Do not add principles not implied by the input
4. Preserve the original intent and tone
5. Structure logically, from general to specific

Generate the Constitution now.
