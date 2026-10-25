-- Retenção por coorte trimestral de contratação: % das apólices ainda ativas k meses após o início.
-- Uma apólice só entra no denominador do mês k se a coorte já completou k meses (:ref_month_idx).
WITH apolice AS (
    SELECT f.policy_id,
           d.year || '-T' || d.quarter AS coorte,
           d.year * 12 + d.month - 1   AS mes_inicio_idx
    FROM fact_policy f
    JOIN dim_date d ON d.date_key = f.start_date_key
),
marcos(k) AS (VALUES (0), (3), (6), (12), (18), (24)),
elegivel AS (
    SELECT a.*, m.k
    FROM apolice a CROSS JOIN marcos m
    WHERE a.mes_inicio_idx + m.k <= :ref_month_idx
)
SELECT e.coorte,
       e.k                                          AS meses_desde_inicio,
       COUNT(*)                                     AS apolices,
       ROUND(AVG(COALESCE(pm.is_active_eom, 0)), 4) AS retencao
FROM elegivel e
LEFT JOIN fact_policy_month pm
       ON pm.policy_id = e.policy_id AND pm.months_since_start = e.k
GROUP BY e.coorte, e.k
ORDER BY e.coorte, e.k;
