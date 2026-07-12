-- Corrige processos sem unidade (legado / dump).
-- Rode no Neon se a caixa continuar vazia após o deploy do filtro.

UPDATE processos p
SET
  unidade_origem_id = COALESCE(p.unidade_origem_id, u.unidade_id),
  orgao_origem_id = COALESCE(p.orgao_origem_id, u.orgao_id),
  municipio_origem_id = COALESCE(p.municipio_origem_id, u.municipio_id)
FROM users u
WHERE p.created_by = u.id
  AND (
    p.unidade_origem_id IS NULL
    OR p.orgao_origem_id IS NULL
    OR p.municipio_origem_id IS NULL
  );

UPDATE processos
SET
  unidade_atual_id = COALESCE(unidade_atual_id, unidade_origem_id),
  orgao_atual_id = COALESCE(orgao_atual_id, orgao_origem_id),
  municipio_atual_id = COALESCE(municipio_atual_id, municipio_origem_id)
WHERE unidade_atual_id IS NULL
   OR orgao_atual_id IS NULL
   OR municipio_atual_id IS NULL;
