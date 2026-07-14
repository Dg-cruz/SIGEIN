-- Tabela de ocorrências do CAD (SINESP-like)
CREATE TABLE IF NOT EXISTS cad_ocorrencias (
    id SERIAL PRIMARY KEY,
    protocolo VARCHAR(30) NOT NULL UNIQUE,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id),
    orgao_id INTEGER REFERENCES orgaos(id),
    unidade_id INTEGER REFERENCES unidades(id),
    canal VARCHAR(30) NOT NULL DEFAULT '153',
    prioridade VARCHAR(20) NOT NULL DEFAULT 'rotina',
    status VARCHAR(40) NOT NULL DEFAULT 'em_atendimento',
    data_hora_fato TIMESTAMP WITHOUT TIME ZONE,
    data_hora_registro TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    solicitante_nome VARCHAR(200),
    solicitante_telefone VARCHAR(30),
    solicitante_documento VARCHAR(30),
    solicitante_anonimo BOOLEAN DEFAULT FALSE,
    tipo_natureza VARCHAR(20) NOT NULL DEFAULT 'atipica',
    natureza_codigo VARCHAR(50) NOT NULL,
    natureza_nome VARCHAR(200) NOT NULL,
    natureza_grupo VARCHAR(100),
    meio_empregado VARCHAR(40) NOT NULL DEFAULT 'nao_houve',
    tentado BOOLEAN DEFAULT FALSE,
    em_evento BOOLEAN DEFAULT FALSE,
    evento_descricao VARCHAR(200),
    cep VARCHAR(9),
    logradouro VARCHAR(255),
    numero VARCHAR(20),
    complemento VARCHAR(120),
    bairro VARCHAR(120),
    cidade VARCHAR(120),
    uf VARCHAR(2),
    ponto_referencia VARCHAR(255),
    endereco_sem_cep BOOLEAN DEFAULT FALSE,
    relato TEXT,
    observacao TEXT,
    created_by INTEGER NOT NULL REFERENCES users(id),
    updated_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_cad_ocorrencias_id ON cad_ocorrencias (id);
CREATE INDEX IF NOT EXISTS ix_cad_ocorrencias_protocolo ON cad_ocorrencias (protocolo);
CREATE INDEX IF NOT EXISTS ix_cad_ocorrencias_municipio ON cad_ocorrencias (municipio_id);
CREATE INDEX IF NOT EXISTS ix_cad_ocorrencias_status ON cad_ocorrencias (status);
