-- Funil da jornada digital por produto: sessões que chegaram a cada etapa e conversão entre etapas.
WITH sessao AS (
    SELECT session_id, product_key, MAX(step_order) AS etapa_max
    FROM fact_funnel_event
    WHERE date_key BETWEEN :start_key AND :end_key
    GROUP BY session_id, product_key
)
SELECT p.product_name                                            AS produto,
       COUNT(*)                                                  AS ofertas_visualizadas,
       SUM(etapa_max >= 1)                                       AS simulacoes,
       SUM(etapa_max >= 2)                                       AS propostas,
       SUM(etapa_max >= 3)                                       AS contratacoes,
       ROUND(1.0 * SUM(etapa_max >= 1) / COUNT(*), 4)            AS conv_oferta_simulacao,
       ROUND(1.0 * SUM(etapa_max >= 2) / SUM(etapa_max >= 1), 4) AS conv_simulacao_proposta,
       ROUND(1.0 * SUM(etapa_max >= 3) / SUM(etapa_max >= 2), 4) AS conv_proposta_contratacao,
       ROUND(1.0 * SUM(etapa_max >= 3) / COUNT(*), 4)            AS conversao_total
FROM sessao s
JOIN dim_product p ON p.product_key = s.product_key
GROUP BY p.product_name
ORDER BY conversao_total DESC;
