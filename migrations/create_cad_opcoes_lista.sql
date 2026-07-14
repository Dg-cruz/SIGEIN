-- Opções configuráveis dos selects do CAD
CREATE TABLE IF NOT EXISTS cad_opcoes_lista (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id),
    tipo VARCHAR(40) NOT NULL,
    codigo VARCHAR(50) NOT NULL,
    label VARCHAR(200) NOT NULL,
    extra1 VARCHAR(120),
    extra2 VARCHAR(50),
    ordem INTEGER DEFAULT 0,
    ativo BOOLEAN DEFAULT TRUE,
    sistema BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_cad_opcoes_lista_id ON cad_opcoes_lista (id);
CREATE INDEX IF NOT EXISTS ix_cad_opcoes_lista_municipio ON cad_opcoes_lista (municipio_id);
CREATE INDEX IF NOT EXISTS ix_cad_opcoes_lista_tipo ON cad_opcoes_lista (tipo);
CREATE UNIQUE INDEX IF NOT EXISTS uq_cad_opcoes_municipio_tipo_codigo
    ON cad_opcoes_lista (municipio_id, tipo, codigo);
