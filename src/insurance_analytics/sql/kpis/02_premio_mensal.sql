-- Evolução mensal da carteira por produto: prêmio ganho, apólices ativas, vendas e cancelamentos.
SELECT d.year_month                     AS mes,
       p.product_name                   AS produto,
       ROUND(SUM(pm.earned_premium), 2) AS premio_ganho,
       SUM(pm.is_active_eom)            AS apolices_ativas_fim_mes,
       SUM(pm.is_new)                   AS novas_apolices,
       SUM(pm.is_cancelled)             AS cancelamentos
FROM fact_policy_month pm
JOIN dim_date    d ON d.date_key    = pm.month_key
JOIN dim_product p ON p.product_key = pm.product_key
GROUP BY d.year_month, p.product_name
ORDER BY d.year_month, p.product_name;
