-- Analytical Base Table do modelo de cancelamento em 12 meses.
-- Todas as variáveis são conhecidas no momento da contratação (sem vazamento de informação futura).
SELECT f.policy_id,
       p.product_name                     AS produto,
       ch.channel_name                    AS canal,
       f.payment_method                   AS meio_pagamento,
       c.income_band                      AS faixa_renda,
       c.segment                          AS segmento,
       c.region                           AS regiao,
       c.gender                           AS genero,
       f.customer_age_at_start            AS idade,
       f.monthly_premium                  AS premio_mensal,
       f.monthly_premium / p.base_premium AS premio_relativo,
       COUNT(*) OVER (PARTITION BY f.customer_key
                      ORDER BY f.start_date_key, f.policy_id
                      ROWS UNBOUNDED PRECEDING)             AS produtos_na_contratacao,
       (ds.year * 12 + ds.month) - (da.year * 12 + da.month) AS meses_de_conta,
       ds.full_date                       AS data_inicio,
       CASE WHEN f.status = 'cancelada' AND f.tenure_days < 365 THEN 1 ELSE 0 END AS cancelou_12m
FROM fact_policy f
JOIN dim_product  p  ON p.product_key  = f.product_key
JOIN dim_channel  ch ON ch.channel_key = f.channel_key
JOIN dim_customer c  ON c.customer_key = f.customer_key
JOIN dim_date     ds ON ds.date_key    = f.start_date_key
LEFT JOIN dim_date da ON da.date_key   = c.account_open_date_key
WHERE f.start_date_key <= :cutoff_key;
