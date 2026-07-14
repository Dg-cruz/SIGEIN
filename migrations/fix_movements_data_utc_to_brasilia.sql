-- Corrige horário das movimentações gravadas em UTC (3h à frente de Brasília).
-- Rode uma vez em cada ambiente (local / Neon). Depois do deploy do fix, novos registros já usam horário local.

UPDATE movements
SET data = data - INTERVAL '3 hours'
WHERE data IS NOT NULL;
