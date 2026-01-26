# Céu Interno — Melhorias de UX, Design e Produto

Este documento reúne recomendações para tornar o app **Céu Interno** mais confiável, claro e coerente com a proposta de astrologia psicológica, mantendo a **estrutura atual** das telas/abas (Onboarding, Hoje, Mapa, Ano, Mais).

## Objetivos
- **Confiabilidade**: reduzir falhas de carregamento e, quando ocorrerem, exibir um resumo estável e humanizado.
- **Clareza**: reforçar a proposta premium e o valor do trial.
- **Evolução contínua**: adicionar recursos compatíveis com a arquitetura atual, sem alterar a navegação.

## Recomendações por tela

### Onboarding + Cadastro
- **Mensagem mais persuasiva em 3 slides**:
  1. "Astrologia psicológica para te ajudar a viver melhor."
  2. "Entenda seus padrões com linguagem acolhedora e prática."
  3. "Receba um resumo diário com foco emocional e relacional."
- **Data/hora mais acessíveis**:
  - Permitir digitação de data e seleção direta de ano.
  - Adicionar opção “**não sei a hora exata**” para reduzir fricção.

### Hoje
- **Topo mais claro**: frase‑chave do dia + ícones de eixos (emoções/relacionamentos/trabalho/corpo).
- **Fallback inteligente**: quando falhar o backend, gerar um resumo estável com linguagem humanizada, evitando erros técnicos.
- **CTA para análise aprofundada** mantido, com visual mais destacado.

### Mapa
- **Até o mapa interativo chegar**: priorizar "Aspectos dominantes" e adicionar texto: "Em breve: distribuições completas do mapa".
- **Evolução futura**:
  - Tooltips para planetas e casas.
  - Exportação do mapa em imagem.
  - Sinastria básica com comparativo simples.

### Ano
- **Começar com 7 dias**: lista com ícone + frase por dia.
- **Destaques**: evidenciar eclipses, retrogradações, retornos e transições marcantes.
- **Escalar gradualmente**: 7 → 14 → 30 dias conforme estabilidade.

### Mais
- **Centro de confiança**: incluir gestão de conta, dados pessoais, privacidade e histórico.
- **Plano Premium**: comparativo claro entre Free/Trial/Premium e datas do trial.
- **Sinastria**: explicar benefícios mesmo antes de lançar a funcionalidade.

## Funcionalidades novas compatíveis
- **Mini‑jornadas de autocuidado**: rotinas diárias alinhadas ao clima do dia.
- **Alertas personalizados**: avisos de aspectos com dicas práticas.
- **Sinastria básica**: comparação simples de dois mapas.
- **Integração com calendário**: exportar previsões.
- **Compartilhamento social**: imagens do mapa ou do resumo diário.

## Tom e narrativa
- Sempre **humanizado e construtivo**, evitando linguagem fatalista.
- Exemplo de copy: “tendência”, “convite”, “ajuste”, “cuidado”, “clareza”.

## Observação final
As recomendações acima **não alteram a estrutura de navegação** e podem ser integradas de forma incremental, começando por melhorias de confiabilidade e clareza premium.
