-- Impede marcas duplicadas (case-insensitive).
-- Pré-requisito: não pode haver nomes repetidos em brands.

CREATE UNIQUE INDEX IF NOT EXISTS uq_brands_nome_lower
ON brands (lower(btrim(nome)));
