# Dicionário de métricas

Definições usadas em todas as consultas de [`sql/kpis/`](../src/insurance_analytics/sql/kpis). Uma métrica tem uma
única definição — se o número de dois relatórios diverge, a causa é o filtro, nunca a fórmula.

| Métrica | Definição | Fonte | Consulta |
|---|---|---|---|
| **Apólices ativas** | apólices com `status = 'ativa'` na data de referência | `fact_policy` | 01 |
| **Produtos por cliente** | apólices ativas ÷ clientes distintos com apólice ativa | `fact_policy` | 01 |
| **Ticket médio** | média do prêmio mensal das apólices ativas | `fact_policy` | 01 |
| **Prêmio ganho** | Σ prêmio mensal × dias de cobertura no mês ÷ dias do mês | `fact_policy_month` | 01, 02, 03 |
| **Sinistro incorrido** | valor pago dos avisos aprovados + valor avisado dos avisos em análise (reserva) | `fact_claim` | 01, 03 |
| **Sinistralidade** | sinistro incorrido ÷ prêmio ganho, no mesmo período | ambas | 01, 03 |
| **Frequência anual** | avisos ÷ anos de exposição (Σ dias de cobertura ÷ 365,25) | ambas | 03 |
| **Severidade média** | sinistro incorrido ÷ avisos não negados | `fact_claim` | 03 |
| **Taxa de negativa** | avisos negados ÷ avisos | `fact_claim` | 03 |
| **Cancelamento em 12 meses** | apólices canceladas com menos de 365 dias de vigência ÷ apólices com ≥ 12 meses de observação | `fact_policy` | 04 |
| **Conversão do funil** | sessões que chegaram à etapa *n* ÷ sessões que chegaram à etapa *n-1* | `fact_funnel_event` | 05 |
| **Retenção da coorte (Mk)** | apólices ativas no fim do mês *k* após a contratação ÷ apólices da coorte que já completaram *k* meses | `fact_policy_month` | 06 |
| **Participação no prêmio** | prêmio mensal do grupo ÷ prêmio mensal total da carteira ativa | `fact_policy` | 07 |

## Parâmetros

| Parâmetro | Padrão | Significado |
|---|---|---|
| `:start_key` / `:end_key` | 20250101 / 20251231 | período analisado |
| `:cutoff_key` | 20241231 | última data de início com 12 meses de maturação |
| `:ref_month_idx` | dez/2025 | último mês completo observado (coortes) |

Os parâmetros são definidos em [`kpis.default_params`](../src/insurance_analytics/kpis.py) e podem ser sobrescritos em
`kpis.run_all(paths, params={...})`.

## Cuidados de interpretação

- **Sinistralidade com poucos avisos é instável.** Sempre ler a taxa junto com a quantidade de avisos.
- **Cancelamento só para apólices maduras.** Incluir apólices recentes subestimaria o churn (ainda não tiveram tempo de cancelar).
- **Coortes recentes têm menos marcos.** Uma coorte de 2025-T3 só tem M0 e M3 — a ausência de M6 não é zero.
