# Modelo de dados

O data mart segue a modelagem dimensional de Kimball: **dimensões conformadas** compartilhadas por várias tabelas
fato, cada uma com um **grão** bem definido. DDL completa em [`schema.sql`](../src/insurance_analytics/sql/schema.sql).

## Diagrama

```mermaid
erDiagram
    dim_customer ||--o{ fact_policy : contrata
    dim_product  ||--o{ fact_policy : ""
    dim_channel  ||--o{ fact_policy : ""
    dim_date     ||--o{ fact_policy : "início / cancelamento"
    fact_policy  ||--|{ fact_policy_month : "explode em meses"
    fact_policy  ||--o{ fact_claim : "gera avisos"
    dim_date     ||--o{ fact_claim : ""
    dim_customer ||--o{ fact_funnel_event : navega
    dim_product  ||--o{ fact_funnel_event : ""
    dim_date     ||--o{ fact_funnel_event : ""

    dim_customer {
        int customer_key PK
        text state
        text region
        text income_band
        text segment
        text age_band
    }
    dim_product {
        int product_key PK
        text product_name
        text category
        real base_premium
    }
    dim_channel {
        int channel_key PK
        text channel_name
        text channel_type
    }
    dim_date {
        int date_key PK "yyyymmdd"
        text full_date
        int year
        int month
        text year_month
    }
    fact_policy {
        int policy_id PK
        int customer_key FK
        int product_key FK
        int channel_key FK
        int start_date_key FK
        int cancel_date_key FK
        text status
        real monthly_premium
        int tenure_days
    }
    fact_policy_month {
        int policy_id PK
        int month_key PK
        int exposure_days
        real earned_premium
        int is_new
        int is_cancelled
        int is_active_eom
    }
    fact_claim {
        int claim_id PK
        int policy_id FK
        int claim_date_key FK
        text claim_status
        real claim_amount
        real paid_amount
    }
    fact_funnel_event {
        int event_id PK
        int session_id
        int product_key FK
        int date_key FK
        text step
        int step_order
    }
```

## Tabelas fato

| Tabela | Grão | Tipo | Uso principal |
|---|---|---|---|
| `fact_policy` | 1 linha por apólice | acumulativa (ciclo de vida) | carteira ativa, churn em 12 meses, ABT do modelo |
| `fact_policy_month` | 1 linha por apólice × mês de vigência | snapshot periódico | prêmio ganho, séries mensais, coortes, exposição para frequência |
| `fact_claim` | 1 linha por aviso de sinistro | transacional | sinistralidade, frequência, severidade |
| `fact_funnel_event` | 1 linha por evento da jornada | transacional | funil de conversão |

## Decisões de modelagem

- **Snapshot mensal materializado.** Prêmio ganho e "apólices ativas no fim do mês" exigiriam expandir datas em toda
  consulta. Materializar `fact_policy_month` no ETL deixa os KPIs simples, rápidos e consistentes entre si.
- **Prêmio ganho *pro rata die*.** Apólice iniciada em 17/01 com prêmio de R$ 31 ganha R$ 15 em janeiro (15/31 dias).
  O mês do cancelamento sempre tem linha (mesmo com exposição zero) para que o evento seja contado.
- **Chave de data inteira `yyyymmdd`.** Legível, ordenável e eficiente para filtros por período (`BETWEEN 20250101 AND 20251231`).
- **Valor "ND" em vez de nulo** nas dimensões (UF, região, faixa etária), para que agrupamentos não percam linhas.
- **Quarentena em vez de descarte silencioso.** Linhas que violam regras bloqueantes são gravadas em
  `data/quarantine/` com o motivo, permitindo investigação com a área de origem.
- **Integridade testada.** `tests/test_warehouse.py` valida chaves estrangeiras, unicidade do grão e a consistência
  entre `fact_policy` e o snapshot (ex.: apólices ativas = ativas no fim do último mês).

## Regras de qualidade aplicadas no ETL

| Severidade | Tratamento | Exemplos |
|---|---|---|
| alerta | corrigido | `customer_id`/`policy_id` duplicado → deduplicação; UF minúscula/espaços → padronização; UF nula → `ND`; nascimento no futuro → nulo |
| bloqueante | quarentena | prêmio ≤ 0; cancelamento antes do início; cliente ou apólice órfã; sinistro antes da vigência; pago > avisado |

Resultado da última execução: [`reports/qualidade_dados.md`](../reports/qualidade_dados.md).
