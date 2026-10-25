-- Taxa de cancelamento em até 12 meses (churn) por produto e meio de pagamento.
-- Só entram apólices com pelo menos 12 meses de observação (início até :cutoff_key).
SELECT p.product_name                                                AS produto,
       f.payment_method                                              AS meio_pagamento,
       COUNT(*)                                                      AS apolices,
       SUM(f.status = 'cancelada' AND f.tenure_days < 365)           AS canceladas_12m,
       ROUND(AVG(f.status = 'cancelada' AND f.tenure_days < 365), 4) AS taxa_cancelamento_12m
FROM fact_policy f
JOIN dim_product p ON p.product_key = f.product_key
WHERE f.start_date_key <= :cutoff_key
GROUP BY p.product_name, f.payment_method
ORDER BY p.product_name, f.payment_method;
