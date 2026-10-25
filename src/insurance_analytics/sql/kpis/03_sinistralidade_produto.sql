-- Sinistralidade, frequência e severidade por produto no período [:start_key, :end_key].
-- Frequência = avisos / anos de exposição; severidade = incorrido médio por aviso não negado.
WITH exposicao AS (
    SELECT product_key,
           SUM(earned_premium)         AS premio_ganho,
           SUM(exposure_days) / 365.25 AS anos_exposicao
    FROM fact_policy_month
    WHERE month_key BETWEEN :start_key AND :end_key
    GROUP BY product_key
),
sinistros AS (
    SELECT product_key,
           COUNT(*)                     AS avisos,
           SUM(claim_status = 'negado') AS negados,
           SUM(CASE WHEN claim_status = 'aprovado'   THEN paid_amount
                    WHEN claim_status = 'em_analise' THEN claim_amount
                    ELSE 0 END)         AS sinistro_incorrido
    FROM fact_claim
    WHERE claim_date_key BETWEEN :start_key AND :end_key
    GROUP BY product_key
)
SELECT p.product_name                                                   AS produto,
       p.category                                                       AS categoria,
       ROUND(e.premio_ganho, 2)                                         AS premio_ganho,
       ROUND(COALESCE(s.sinistro_incorrido, 0), 2)                      AS sinistro_incorrido,
       ROUND(COALESCE(s.sinistro_incorrido, 0) / e.premio_ganho, 4)     AS sinistralidade,
       COALESCE(s.avisos, 0)                                            AS avisos,
       ROUND(COALESCE(s.avisos, 0) / e.anos_exposicao, 4)               AS frequencia_anual,
       ROUND(s.sinistro_incorrido / NULLIF(s.avisos - s.negados, 0), 2) AS severidade_media,
       ROUND(1.0 * s.negados / NULLIF(s.avisos, 0), 4)                  AS taxa_negativa
FROM exposicao e
JOIN dim_product p ON p.product_key = e.product_key
LEFT JOIN sinistros s ON s.product_key = e.product_key
ORDER BY sinistralidade DESC;
