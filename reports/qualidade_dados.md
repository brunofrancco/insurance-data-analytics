# Relatório de qualidade de dados (base bruta)

Regras avaliadas: **15** · com falha: **11** · linhas afetadas: **772**

| regra                              | tabela         | dimensao     | severidade   | descricao                                                   |   linhas_com_falha |   pct_falha | status   |
|:-----------------------------------|:---------------|:-------------|:-------------|:------------------------------------------------------------|-------------------:|------------:|:---------|
| clientes_id_duplicado              | customers      | unicidade    | alerta       | customer_id repetido                                        |                100 |     0.00498 | FALHA    |
| clientes_uf_nula                   | customers      | completude   | alerta       | UF não informada                                            |                199 |     0.0099  | FALHA    |
| clientes_uf_invalida               | customers      | validade     | alerta       | UF fora do padrão (minúscula, espaços ou sigla inexistente) |                200 |     0.00995 | FALHA    |
| clientes_nascimento_futuro         | customers      | validade     | alerta       | data de nascimento posterior à data de referência           |                 40 |     0.00199 | FALHA    |
| apolices_id_duplicado              | policies       | unicidade    | alerta       | policy_id repetido                                          |                 87 |     0.00301 | FALHA    |
| apolices_premio_nao_positivo       | policies       | validade     | bloqueante   | prêmio mensal menor ou igual a zero                         |                 57 |     0.00197 | FALHA    |
| apolices_cancelamento_antes_inicio | policies       | consistência | bloqueante   | data de cancelamento anterior ao início de vigência         |                 35 |     0.00121 | FALHA    |
| apolices_status_inconsistente      | policies       | consistência | bloqueante   | status 'cancelada' sem data de cancelamento (ou o inverso)  |                  0 |     0       | OK       |
| apolices_cliente_orfao             | policies       | integridade  | bloqueante   | customer_id inexistente na base de clientes                 |                 28 |     0.00097 | FALHA    |
| sinistros_apolice_orfa             | claims         | integridade  | bloqueante   | policy_id inexistente na base de apólices                   |                  4 |     0.00092 | FALHA    |
| sinistros_antes_vigencia           | claims         | consistência | bloqueante   | sinistro com data anterior ao início da apólice             |                 12 |     0.00277 | FALHA    |
| sinistros_pago_maior_que_avisado   | claims         | consistência | bloqueante   | valor pago maior que o valor avisado                        |                 10 |     0.00231 | FALHA    |
| sinistros_pago_sem_aprovacao       | claims         | consistência | bloqueante   | pagamento registrado para sinistro não aprovado             |                  0 |     0       | OK       |
| jornada_evento_futuro              | journey_events | validade     | bloqueante   | evento posterior à data de referência                       |                  0 |     0       | OK       |
| jornada_produto_invalido           | journey_events | integridade  | bloqueante   | product_id inexistente no catálogo                          |                  0 |     0       | OK       |

Regras **bloqueantes** enviam a linha para `data/quarantine/`; regras de **alerta** são corrigidas no ETL (deduplicação e padronização).