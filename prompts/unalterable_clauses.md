## Cláusulas Pétreas (Regras Fixas e Inegociáveis)

Toda saída gerada contém e respeita estas regras em todos os projetos:

1. **Excelência Estrutural:** Aplicação rigorosa de SOLID e Object Calisthenics.
2. **Integridade de Testes:** Sucesso é binário (se um teste falha, a tarefa falha). Testes validam o comportamento e a lógica de negócio, não parâmetros hardcoded. Refatorações preservam testes enquanto a lógica permanecer a mesma.
3. **Configuração Externa e Zero Hardcoding:** É terminantemente proibido o uso de valores literais ou parâmetros hardcoded no código (URLs, credenciais, portas, timeouts, limites). Toda variável de ambiente ou ajuste reside em arquivos de configuração (.env). O Agente Executor extrai todo parâmetro configurável para o ambiente; violações desta regra invalidam a entrega.
4. **Modularidade e Desacoplamento:** A arquitetura isola domínios e garante que a comunicação entre componentes ocorra exclusivamente via interfaces ou contratos; o sistema recusa acoplamentos rígidos que impeçam a substituição ou evolução isolada de suas partes funcionais.
5. **Tutorial de Extensibilidade Obrigatório:** Toda funcionalidade nova ou modificada que introduza comportamento configurável, heurístico ou passível de personalização futura acompanha um tutorial técnico explícito documentando sua finalidade, localização da lógica, pontos formais de extensão e procedimento de alteração; a ausência desse tutorial caracteriza a funcionalidade como arquiteturalmente incompleta, configurando dívida técnica ativa e violação direta das cláusulas pétreas.