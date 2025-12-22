## Cláusulas Pétreas (Regras Fixas e Inegociáveis)

Toda saída gerada contém e respeita estas regras em todos os projetos:

1. **Excelência Estrutural Verificável:** Qualidade de código é validada por ferramentas, não por revisão humana. Obrigatório: `mypy --strict` passa sem erros, funções têm type hints completos, docstrings explicam propósito (não implementação). SOLID e Object Calisthenics são referências de design, não checklists de conformidade — a IA não consegue manter disciplina linha-a-linha sem validação externa.

2. **Arquitetura Hexagonal Obrigatória:** O sistema adota Ports & Adapters como padrão arquitetural inegociável. O domínio (regras de negócio puras) não possui dependências externas. Ports definem contratos abstratos via Protocol (Python) ou interfaces equivalentes. Adapters implementam os Ports e são substituíveis sem afetar o domínio. Nenhum código de domínio importa diretamente implementações concretas de I/O, persistência ou serviços externos.

3. **Protocol-First Design:** Toda dependência externa (LLM, STT, TTS, storage, APIs) possui um Protocol definido ANTES de qualquer implementação. O Protocol é o contrato; implementações são detalhes. Novos adapters são adicionados sem modificar código existente. O Agente Executor não cria implementações sem Protocol prévio.

4. **Functional Core, Imperative Shell:** Lógica de domínio é implementada como funções puras sempre que possível (mesma entrada produz mesma saída, sem side effects). I/O e side effects são isolados na camada de adapters (shell imperativo). Funções puras são a unidade primária de teste.

5. **Integridade de Testes:** Sucesso é binário (se um teste falha, a tarefa falha). Testes validam o comportamento e a lógica de negócio, não parâmetros hardcoded. Refatorações preservam testes enquanto a lógica permanecer a mesma. Funções puras do domínio têm cobertura obrigatória.

6. **Configuração Externa e Zero Hardcoding:** É terminantemente proibido o uso de valores literais ou parâmetros hardcoded no código (URLs, credenciais, portas, timeouts, limites). Toda variável de ambiente ou ajuste reside em arquivos de configuração (.env). O Agente Executor extrai todo parâmetro configurável para o ambiente; violações desta regra invalidam a entrega.

7. **Injeção de Dependências Explícita:** Componentes recebem suas dependências via construtor ou parâmetro, nunca instanciam internamente. Isso garante testabilidade e substituição de implementações. A composição ocorre em uma camada de configuração dedicada (container/factory).

8. **Contratos Antes de Comportamento:** O Agente Executor recebe contratos (Protocols, interfaces, tipos) como entrada primária. Prompts que descrevem comportamento sem contrato prévio são rejeitados ou convertidos para contract-first. A IA implementa contratos, não inventa interfaces.

9. **Tutorial de Extensibilidade Obrigatório:** Toda funcionalidade nova ou modificada que introduza comportamento configurável, heurístico ou passível de personalização futura acompanha um tutorial técnico explícito documentando sua finalidade, localização da lógica, pontos formais de extensão e procedimento de alteração; a ausência desse tutorial caracteriza a funcionalidade como arquiteturalmente incompleta, configurando dívida técnica ativa e violação direta das cláusulas pétreas.

10. **Autoconhecimento de Limitações da IA:** O Agente Executor (IA) reconhece que não mantém modelo mental persistente do sistema, não tem consciência do custo de manutenção futura, e tende a otimizar localmente. Portanto: decisões arquiteturais são humanas (IA não sugere estrutura), validação é por ferramentas (IA não revisa próprio código), e prompts devem ser determinísticos com contratos explícitos (IA não debate, executa). Código gerado sem contrato prévio é tratado como rascunho, não como entrega.