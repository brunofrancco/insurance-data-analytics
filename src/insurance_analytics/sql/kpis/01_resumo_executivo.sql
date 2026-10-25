-- Indicadores de cabeçalho do período [:start_key, :end_key].
-- Sinistro incorrido = valor pago (aprovados) + valor avisado ainda em análise (reserva).
WITH premio AS (
    SELECT SUM(earned_premium) AS premio_ganho
    FROM fact_policy_month
    WHERE month_key BETWEEN :start_key AND :end_key
),
sinistros AS (
    SELECT COUNT(*) AS avisos,
           SUM(paid_amount) + SUM(CASE WHEN claim_status = 'em_analise' THEN claim_amount ELSE 0 END) AS sinistro_incorrido
    FROM fact_claim
    WHERE claim_date_key BETWEEN :start_key AND :end_key
),
carteira AS (
    SELECT COUNT(*)                     AS apolices_ativas,
           COUNT(DISTINCT customer_key) AS clientes_ativos,
           AVG(monthly_premium)         AS ticket_medio
    FROM fact_policy
    WHERE status = 'ativa'
),
movimento AS (
    SELECT SUM(start_date_key  BETWEEN :start_key AND :end_key) AS novas_apolices,
           SUM(cancel_date_key BETWEEN :start_key AND :end_key) AS cancelamentos
    FROM fact_policy
)
SELECT c.apolices_ativas,
       c.clientes_ativos,
       ROUND(1.0 * c.apolices_ativas / c.clientes_ativos, 3) AS produtos_por_cliente,
       ROUND(c.ticket_medio, 2)                              AS ticket_medio,
       m.novas_apolices,
       m.cancelamentos,
       ROUND(p.premio_ganho, 2)                              AS premio_ganho,
       ROUND(s.sinistro_incorrido, 2)                        AS sinistro_incorrido,
       ROUND(s.sinistro_incorrido / p.premio_ganho, 4)       AS sinistralidade,
       s.avisos                                              AS avisos_sinistro
FROM carteira c, movimento m, premio p, sinistros s;
