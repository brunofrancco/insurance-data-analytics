-- Carteira ativa por região e faixa etária, com participação no prêmio mensal.
SELECT c.region                                                                AS regiao,
       c.age_band                                                              AS faixa_etaria,
       COUNT(*)                                                                AS apolices_ativas,
       ROUND(SUM(f.monthly_premium), 2)                                        AS premio_mensal,
       ROUND(SUM(f.monthly_premium) / SUM(SUM(f.monthly_premium)) OVER (), 4) AS participacao_premio
FROM fact_policy f
JOIN dim_customer c ON c.customer_key = f.customer_key
WHERE f.status = 'ativa'
GROUP BY c.region, c.age_band
ORDER BY premio_mensal DESC;
