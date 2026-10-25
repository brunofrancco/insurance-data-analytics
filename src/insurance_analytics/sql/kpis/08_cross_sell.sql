-- Distribuição de clientes ativos pela quantidade de produtos (oportunidade de cross-sell).
WITH por_cliente AS (
    SELECT customer_key, COUNT(DISTINCT product_key) AS produtos
    FROM fact_policy
    WHERE status = 'ativa'
    GROUP BY customer_key
)
SELECT produtos                                         AS qtd_produtos,
       COUNT(*)                                         AS clientes,
       ROUND(1.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 4) AS pct_clientes
FROM por_cliente
GROUP BY produtos
ORDER BY produtos;
