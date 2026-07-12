-- Ajusta processos no Neon para aceitar NULL (igual ao banco local).
-- Rode no SQL Editor ANTES de reimportar o dump de dados.

ALTER TABLE processos ALTER COLUMN municipio_origem_id DROP NOT NULL;
ALTER TABLE processos ALTER COLUMN orgao_origem_id DROP NOT NULL;
ALTER TABLE processos ALTER COLUMN unidade_origem_id DROP NOT NULL;
ALTER TABLE processos ALTER COLUMN municipio_atual_id DROP NOT NULL;
ALTER TABLE processos ALTER COLUMN orgao_atual_id DROP NOT NULL;
ALTER TABLE processos ALTER COLUMN unidade_atual_id DROP NOT NULL;
