# Tutorial: Adding Custom Oracles

This guide shows how to create and configure custom oracle personalities for the contextual feedback system.

## What is an Oracle?

An oracle is a personalized AI assistant that provides contextual feedback on your voice recordings. Each oracle has a unique personality defined by a markdown file containing instructions and a placeholder for context injection.

## Quick Start

1. Navigate to the oracles directory:
   ```
   prompts/oracles/
   ```

2. Create a new markdown file (e.g., `mentor.md`):
   ```markdown
   # Mentor

   You are a supportive mentor who provides constructive guidance.
   
   When reviewing the user's content, focus on:
   - Identifying strengths and what's working well
   - Suggesting improvements with actionable steps
   - Encouraging experimentation and learning

   {{CONTEXT}}

   Provide your feedback in a warm, supportive tone.
   ```

3. The new oracle will appear automatically in the Telegram keyboard (after ~10 seconds due to cache refresh).

## Oracle File Structure

### Required Elements

1. **H1 Heading (Oracle Name)**:
   The first H1 heading (`# Name`) becomes the oracle's display name in the Telegram button.

2. **Prompt Instructions**:
   The body of the markdown describes the oracle's personality and how it should respond.

3. **Context Placeholder** (`{{CONTEXT}}`):
   This placeholder is replaced with the user's session transcripts and prior LLM responses.

### Example Structure

```markdown
# Oracle Name

[Personality description and instructions]

{{CONTEXT}}

[Optional closing instructions]
```

## Best Practices

### 1. Clear Personality Definition

Define what makes this oracle unique:

```markdown
# Cético Profissional

Você é um pensador cético que:
- Questiona premissas e suposições
- Identifica riscos e pontos fracos
- Sugere verificações e validações
- Mantém tom construtivo, não destrutivo
```

### 2. Context Positioning

Place `{{CONTEXT}}` where the oracle should receive the user's content:

- **Beginning**: Oracle sees context first, then responds
- **Middle**: Context surrounded by instructions
- **End**: Instructions first, context for reference

### 3. Response Format Guidance

Specify how the oracle should structure its response:

```markdown
Estruture sua análise assim:
1. Resumo dos pontos principais
2. Aspectos positivos identificados
3. Áreas para investigação
4. Próximos passos sugeridos
```

### 4. Language Matching

Match the oracle's language to your audience:

```markdown
# Pragmatic Advisor

[Instructions in English for English-speaking users]
```

```markdown
# Conselheiro Pragmático

[Instruções em português para usuários brasileiros]
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ORACLES_DIR` | `prompts/oracles` | Directory containing oracle files |
| `ORACLE_PLACEHOLDER` | `{{CONTEXT}}` | Placeholder string for context injection |
| `ORACLE_CACHE_TTL` | `10` | Seconds before rescanning directory |
| `LLM_TIMEOUT_SECONDS` | `30` | Timeout for LLM API requests |

### Cache Behavior

Oracle files are cached for performance. Changes are detected automatically after `ORACLE_CACHE_TTL` seconds. To force immediate detection:

1. Send any voice message to trigger a new transcription
2. Or wait for the cache TTL to expire

## Example Oracles

### The Skeptic (Cético)

```markdown
# Cético

Você é um cético construtivo que ajuda a fortalecer ideias através de questionamento rigoroso.

## Sua Abordagem

- Identifique premissas não declaradas
- Questione a lógica e evidências
- Sugira cenários alternativos
- Mantenha respeito pelo autor

{{CONTEXT}}

## Formato de Resposta

Estruture assim:
1. **Premissas Identificadas**: O que está sendo assumido?
2. **Questionamentos**: Perguntas que merecem reflexão
3. **Riscos**: Possíveis problemas ou armadilhas
4. **Sugestão**: Um próximo passo para investigação
```

### The Visionary (Visionário)

```markdown
# Visionário

Você é um visionário que expande possibilidades e identifica oportunidades.

## Sua Missão

Olhe além do óbvio e:
- Conecte ideias de domínios diferentes
- Identifique tendências e padrões emergentes
- Sugira expansões ambiciosas
- Inspire coragem para inovar

{{CONTEXT}}

Responda com entusiasmo e ousadia criativa.
```

### The Optimist (Otimista)

```markdown
# Otimista

Você é um otimista prático que encontra o valor em cada ideia.

## Princípios

- Todo conceito tem potencial
- Foco no que está funcionando
- Builds sobre pontos fortes
- Celebra o progresso

{{CONTEXT}}

Forneça feedback encorajador e específico.
```

## Troubleshooting

### Oracle Not Appearing

1. Check file extension is `.md`
2. Verify file is not empty
3. Wait for cache TTL (default 10 seconds)
4. Check logs for parsing errors

### Placeholder Not Replaced

1. Verify placeholder matches config (`{{CONTEXT}}` by default)
2. Check for typos or extra spaces
3. If no placeholder found, context is appended at end

### LLM Timeout

1. Check `LLM_TIMEOUT_SECONDS` (default 30s)
2. Verify LLM provider is configured (`NARRATE_PROVIDER`)
3. Check API key validity

## Advanced: Spiral Feedback

When "LLM History" is enabled (default), oracles can see previous oracle responses:

1. You ask Cético for feedback
2. Cético analyzes and responds
3. You then ask Visionário
4. Visionário sees both your transcript AND Cético's response
5. Visionário can build upon or contrast with Cético's analysis

This creates a "spiral" of deepening analysis where each oracle contributes a unique perspective while being aware of prior feedback.

To disable this behavior:
- Click the "🔗 Histórico: ON" toggle button to switch to "OFF"
- When OFF, oracles only see transcripts, not prior LLM responses

## See Also

- [Context Management Tutorial](tutorial_context_management.md)
- [Telegram Interaction Guide](telegram_interaction_guide.md)
