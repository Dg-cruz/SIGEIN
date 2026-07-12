-- SIGEIN schema (PostgreSQL / Neon)
-- Execute este arquivo INTEIRO no SQL Editor antes do dump de dados.
-- Sem BEGIN/COMMIT para o Neon nao reverter tudo se uma stmt falhar no meio.

-- brands
CREATE TABLE IF NOT EXISTS brands (
	id SERIAL NOT NULL, 
	nome VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
);

CREATE INDEX IF NOT EXISTS ix_brands_id ON brands (id);

-- categories
CREATE TABLE IF NOT EXISTS categories (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	descricao TEXT, 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
);

CREATE INDEX IF NOT EXISTS ix_categories_id ON categories (id);

-- equipment_states
CREATE TABLE IF NOT EXISTS equipment_states (
	id SERIAL NOT NULL, 
	nome VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
);

CREATE INDEX IF NOT EXISTS ix_equipment_states_id ON equipment_states (id);

-- estados
CREATE TABLE IF NOT EXISTS estados (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	uf VARCHAR(2) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome), 
	UNIQUE (uf)
);

CREATE INDEX IF NOT EXISTS ix_estados_id ON estados (id);

-- grupos
CREATE TABLE IF NOT EXISTS grupos (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	ativo BOOLEAN, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_grupos_id ON grupos (id);

-- paiol_classes_material
CREATE TABLE IF NOT EXISTS paiol_classes_material (
	id SERIAL NOT NULL, 
	codigo VARCHAR(30) NOT NULL, 
	nome VARCHAR(120) NOT NULL, 
	descricao TEXT, 
	grupo_compatibilidade VARCHAR(30), 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE INDEX IF NOT EXISTS ix_paiol_classes_material_id ON paiol_classes_material (id);

-- paiol_fabricantes
CREATE TABLE IF NOT EXISTS paiol_fabricantes (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	pais VARCHAR(80), 
	cnpj VARCHAR(20), 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (nome)
);

CREATE INDEX IF NOT EXISTS ix_paiol_fabricantes_id ON paiol_fabricantes (id);

-- paiol_fornecedores
CREATE TABLE IF NOT EXISTS paiol_fornecedores (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	cnpj VARCHAR(20), 
	contato VARCHAR(200), 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_fornecedores_id ON paiol_fornecedores (id);

-- paiol_tipos_material
CREATE TABLE IF NOT EXISTS paiol_tipos_material (
	id SERIAL NOT NULL, 
	codigo VARCHAR(40) NOT NULL, 
	categoria VARCHAR(50) NOT NULL, 
	especie VARCHAR(200) NOT NULL, 
	descricao TEXT, 
	detalhes JSON, 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (codigo)
);

CREATE INDEX IF NOT EXISTS ix_paiol_tipos_material_id ON paiol_tipos_material (id);

-- produtos_segem
CREATE TABLE IF NOT EXISTS produtos_segem (
	id SERIAL NOT NULL, 
	codigo VARCHAR(100) NOT NULL, 
	descricao TEXT, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_produtos_segem_id ON produtos_segem (id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_produtos_segem_codigo ON produtos_segem (codigo);

-- requerentes
CREATE TABLE IF NOT EXISTS requerentes (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	tipo_documento VARCHAR(20) NOT NULL, 
	numero_documento VARCHAR(20) NOT NULL, 
	email VARCHAR(200), 
	cep VARCHAR(10) NOT NULL, 
	endereco VARCHAR(300) NOT NULL, 
	numero_endereco VARCHAR(20) NOT NULL, 
	bairro VARCHAR(100) NOT NULL, 
	complemento VARCHAR(100), 
	cidade VARCHAR(200) NOT NULL, 
	uf VARCHAR(2) NOT NULL, 
	telefone1 VARCHAR(20), 
	telefone2 VARCHAR(20), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_requerentes_id ON requerentes (id);

-- units
CREATE TABLE IF NOT EXISTS units (
	id SERIAL NOT NULL, 
	name VARCHAR(150) NOT NULL, 
	manager VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE INDEX IF NOT EXISTS ix_units_id ON units (id);

-- assuntos
CREATE TABLE IF NOT EXISTS assuntos (
	id SERIAL NOT NULL, 
	grupo_id INTEGER NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(grupo_id) REFERENCES grupos (id)
);

CREATE INDEX IF NOT EXISTS ix_assuntos_id ON assuntos (id);

-- equipment_types
CREATE TABLE IF NOT EXISTS equipment_types (
	id SERIAL NOT NULL, 
	nome VARCHAR(100) NOT NULL, 
	category_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (nome), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE INDEX IF NOT EXISTS ix_equipment_types_id ON equipment_types (id);

-- municipios
CREATE TABLE IF NOT EXISTS municipios (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	codigo_ibge VARCHAR(7), 
	estado_id INTEGER NOT NULL, 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	UNIQUE (codigo_ibge), 
	FOREIGN KEY(estado_id) REFERENCES estados (id)
);

CREATE INDEX IF NOT EXISTS ix_municipios_id ON municipios (id);

-- paiol_municoes
CREATE TABLE IF NOT EXISTS paiol_municoes (
	id SERIAL NOT NULL, 
	codigo VARCHAR(40) NOT NULL, 
	nome_comercial VARCHAR(300) NOT NULL, 
	calibre VARCHAR(80) NOT NULL, 
	fabricante_marca VARCHAR(200), 
	fabricante_id INTEGER, 
	quantidade_tipo VARCHAR(20), 
	quantidade_valor INTEGER, 
	descricao TEXT, 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(fabricante_id) REFERENCES paiol_fabricantes (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_municoes_id ON paiol_municoes (id);

-- brand_equipment_types
CREATE TABLE IF NOT EXISTS brand_equipment_types (
	brand_id INTEGER NOT NULL, 
	type_id INTEGER NOT NULL, 
	PRIMARY KEY (brand_id, type_id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id) ON DELETE CASCADE, 
	FOREIGN KEY(type_id) REFERENCES equipment_types (id) ON DELETE CASCADE
);

-- orgaos
CREATE TABLE IF NOT EXISTS orgaos (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	sigla VARCHAR(20), 
	municipio_id INTEGER NOT NULL, 
	responsavel VARCHAR(200), 
	email VARCHAR(200), 
	telefone VARCHAR(20), 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id)
);

CREATE INDEX IF NOT EXISTS ix_orgaos_id ON orgaos (id);

-- subassuntos
CREATE TABLE IF NOT EXISTS subassuntos (
	id SERIAL NOT NULL, 
	assunto_id INTEGER NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assunto_id) REFERENCES assuntos (id)
);

CREATE INDEX IF NOT EXISTS ix_subassuntos_id ON subassuntos (id);

-- unidades
CREATE TABLE IF NOT EXISTS unidades (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	sigla VARCHAR(20), 
	orgao_id INTEGER NOT NULL, 
	responsavel VARCHAR(200), 
	ramal VARCHAR(10), 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id)
);

CREATE INDEX IF NOT EXISTS ix_unidades_id ON unidades (id);

-- users
CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	cpf VARCHAR(11) NOT NULL, 
	email VARCHAR(200) NOT NULL, 
	password VARCHAR(255) NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	status VARCHAR(9) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	ultimo_acesso TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidades (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

CREATE INDEX IF NOT EXISTS ix_users_id ON users (id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_cpf ON users (cpf);

-- circulares
CREATE TABLE IF NOT EXISTS circulares (
	id SERIAL NOT NULL, 
	numero VARCHAR(50), 
	assunto VARCHAR(500), 
	conteudo TEXT, 
	municipio_remetente_id INTEGER NOT NULL, 
	orgao_remetente_id INTEGER NOT NULL, 
	unidade_remetente_id INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (numero), 
	FOREIGN KEY(municipio_remetente_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_remetente_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_remetente_id) REFERENCES unidades (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_circulares_id ON circulares (id);

-- logs
CREATE TABLE IF NOT EXISTS logs (
	id SERIAL NOT NULL, 
	usuario VARCHAR(50), 
	acao VARCHAR(255), 
	ip VARCHAR(50), 
	data_hora TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	user_id INTEGER, 
	municipio_id INTEGER, 
	user_agent VARCHAR(500), 
	tipo VARCHAR(20) DEFAULT 'operacional' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id)
);

CREATE INDEX IF NOT EXISTS ix_logs_id ON logs (id);

-- paiol_assinaturas
CREATE TABLE IF NOT EXISTS paiol_assinaturas (
	id SERIAL NOT NULL, 
	documento_tipo VARCHAR(40) NOT NULL, 
	documento_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	hash_registro VARCHAR(128) NOT NULL, 
	observacao TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_assinaturas_id ON paiol_assinaturas (id);

-- paiol_dashboard_atalhos
CREATE TABLE IF NOT EXISTS paiol_dashboard_atalhos (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	menu_key VARCHAR(80) NOT NULL, 
	sort_order INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_dashboard_atalhos_id ON paiol_dashboard_atalhos (id);

CREATE INDEX IF NOT EXISTS ix_paiol_dashboard_atalhos_user_id ON paiol_dashboard_atalhos (user_id);

-- paiol_depositos
CREATE TABLE IF NOT EXISTS paiol_depositos (
	id SERIAL NOT NULL, 
	codigo VARCHAR(30) NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	responsavel_id INTEGER, 
	endereco VARCHAR(300), 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidades (id), 
	FOREIGN KEY(responsavel_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_depositos_id ON paiol_depositos (id);

-- paiol_materiais
CREATE TABLE IF NOT EXISTS paiol_materiais (
	id SERIAL NOT NULL, 
	codigo VARCHAR(50) NOT NULL, 
	nome VARCHAR(200) NOT NULL, 
	descricao TEXT, 
	tipo VARCHAR(30) NOT NULL, 
	calibre VARCHAR(80), 
	classe_id INTEGER, 
	fabricante_id INTEGER, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	controla_por_serie BOOLEAN, 
	controla_lote BOOLEAN, 
	quantidade_minima INTEGER, 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (codigo), 
	FOREIGN KEY(classe_id) REFERENCES paiol_classes_material (id), 
	FOREIGN KEY(fabricante_id) REFERENCES paiol_fabricantes (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_materiais_id ON paiol_materiais (id);

-- processos
CREATE TABLE IF NOT EXISTS processos (
	id SERIAL NOT NULL, 
	numero VARCHAR(50), 
	ano INTEGER, 
	assunto VARCHAR(500), 
	requerente VARCHAR(200), 
	conteudo TEXT, 
	municipio_origem_id INTEGER NOT NULL, 
	orgao_origem_id INTEGER NOT NULL, 
	unidade_origem_id INTEGER NOT NULL, 
	municipio_atual_id INTEGER NOT NULL, 
	orgao_atual_id INTEGER NOT NULL, 
	unidade_atual_id INTEGER NOT NULL, 
	status VARCHAR(50), 
	urgente BOOLEAN, 
	nivel_acesso VARCHAR(20), 
	lido_at TIMESTAMP WITHOUT TIME ZONE, 
	atribuido_to_id INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	processo_principal_id INTEGER, 
	arquivado BOOLEAN, 
	arquivado_at TIMESTAMP WITHOUT TIME ZONE, 
	arquivado_por_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_origem_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_origem_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_origem_id) REFERENCES unidades (id), 
	FOREIGN KEY(municipio_atual_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_atual_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_atual_id) REFERENCES unidades (id), 
	FOREIGN KEY(atribuido_to_id) REFERENCES users (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(processo_principal_id) REFERENCES processos (id), 
	FOREIGN KEY(arquivado_por_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_processos_id ON processos (id);

CREATE UNIQUE INDEX IF NOT EXISTS ix_processos_numero ON processos (numero);

-- products
CREATE TABLE IF NOT EXISTS products (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	category_id INTEGER, 
	type_id INTEGER NOT NULL, 
	brand_id INTEGER NOT NULL, 
	model VARCHAR, 
	description TEXT, 
	controla_por_serie BOOLEAN, 
	ativo BOOLEAN, 
	quantidade INTEGER, 
	quantidade_minima INTEGER, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(type_id) REFERENCES equipment_types (id), 
	FOREIGN KEY(brand_id) REFERENCES brands (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

-- segem_itens
CREATE TABLE IF NOT EXISTS segem_itens (
	id SERIAL NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	ano INTEGER, 
	num_tombo_gcm VARCHAR(50), 
	local VARCHAR(200), 
	codigo VARCHAR(100), 
	descricao TEXT, 
	situacao VARCHAR(100), 
	valor_rs FLOAT, 
	entrada_no_siga VARCHAR(100), 
	nota_de_empenho VARCHAR(100), 
	valor_nota_empenho FLOAT, 
	num_nota_fiscal VARCHAR(100), 
	nome_empresa VARCHAR(200), 
	classificacao_asi VARCHAR(100), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_segem_itens_id ON segem_itens (id);

-- circular_destinatarios
CREATE TABLE IF NOT EXISTS circular_destinatarios (
	id SERIAL NOT NULL, 
	circular_id INTEGER NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	unidade_id INTEGER NOT NULL, 
	recebido BOOLEAN, 
	data_recebimento TIMESTAMP WITHOUT TIME ZONE, 
	arquivado BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(circular_id) REFERENCES circulares (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidades (id)
);

CREATE INDEX IF NOT EXISTS ix_circular_destinatarios_id ON circular_destinatarios (id);

-- items
CREATE TABLE IF NOT EXISTS items (
	id SERIAL NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	unit_id INTEGER NOT NULL, 
	tombo BOOLEAN, 
	num_tombo_ou_serie VARCHAR, 
	estado_id INTEGER, 
	status VARCHAR, 
	data_aquisicao DATE, 
	valor_aquisicao FLOAT, 
	garantia_ate DATE, 
	observacao TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(unit_id) REFERENCES unidades (id), 
	UNIQUE (num_tombo_ou_serie), 
	FOREIGN KEY(estado_id) REFERENCES equipment_states (id)
);

-- paiol_localizacoes
CREATE TABLE IF NOT EXISTS paiol_localizacoes (
	id SERIAL NOT NULL, 
	deposito_id INTEGER NOT NULL, 
	codigo VARCHAR(50) NOT NULL, 
	descricao VARCHAR(200), 
	ativo BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_localizacoes_id ON paiol_localizacoes (id);

-- paiol_lotes
CREATE TABLE IF NOT EXISTS paiol_lotes (
	id SERIAL NOT NULL, 
	material_id INTEGER NOT NULL, 
	numero_lote VARCHAR(80) NOT NULL, 
	data_fabricacao DATE, 
	data_validade DATE, 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_lotes_id ON paiol_lotes (id);

-- paiol_requisicoes
CREATE TABLE IF NOT EXISTS paiol_requisicoes (
	id SERIAL NOT NULL, 
	numero VARCHAR(30) NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	solicitante_id INTEGER NOT NULL, 
	unidade_id INTEGER, 
	deposito_id INTEGER, 
	status VARCHAR(30) NOT NULL, 
	observacao TEXT, 
	motivo_rejeicao TEXT, 
	aprovador_id INTEGER, 
	aprovado_em TIMESTAMP WITHOUT TIME ZONE, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	updated_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(solicitante_id) REFERENCES users (id), 
	FOREIGN KEY(unidade_id) REFERENCES unidades (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(aprovador_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_requisicoes_id ON paiol_requisicoes (id);

CREATE INDEX IF NOT EXISTS ix_paiol_requisicoes_numero ON paiol_requisicoes (numero);

-- paiol_usuarios_autorizados
CREATE TABLE IF NOT EXISTS paiol_usuarios_autorizados (
	id SERIAL NOT NULL, 
	user_id INTEGER NOT NULL, 
	deposito_id INTEGER, 
	classe_id INTEGER, 
	operacoes VARCHAR(500), 
	ativo BOOLEAN, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(classe_id) REFERENCES paiol_classes_material (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_usuarios_autorizados_id ON paiol_usuarios_autorizados (id);

-- processo_assinantes
CREATE TABLE IF NOT EXISTS processo_assinantes (
	id SERIAL NOT NULL, 
	processo_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(processo_id) REFERENCES processos (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_processo_assinantes_id ON processo_assinantes (id);

-- product_attachments
CREATE TABLE IF NOT EXISTS product_attachments (
	id SERIAL NOT NULL, 
	product_id INTEGER NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	stored_name VARCHAR(255) NOT NULL, 
	content_type VARCHAR(100) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

-- segem_itens_produtos
CREATE TABLE IF NOT EXISTS segem_itens_produtos (
	id SERIAL NOT NULL, 
	segem_item_id INTEGER NOT NULL, 
	num_tombo_gcm VARCHAR(50), 
	valor_rs FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(segem_item_id) REFERENCES segem_itens (id)
);

CREATE INDEX IF NOT EXISTS ix_segem_itens_produtos_id ON segem_itens_produtos (id);

-- stock
CREATE TABLE IF NOT EXISTS stock (
	id SERIAL NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	unit_id INTEGER NOT NULL, 
	quantidade INTEGER, 
	quantidade_minima INTEGER, 
	localizacao VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(unit_id) REFERENCES unidades (id)
);

-- tramites
CREATE TABLE IF NOT EXISTS tramites (
	id SERIAL NOT NULL, 
	processo_id INTEGER NOT NULL, 
	municipio_origem_id INTEGER, 
	orgao_origem_id INTEGER, 
	unidade_origem_id INTEGER, 
	municipio_destino_id INTEGER NOT NULL, 
	orgao_destino_id INTEGER NOT NULL, 
	unidade_destino_id INTEGER NOT NULL, 
	despacho TEXT, 
	anexo_path VARCHAR(500), 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	created_by INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(processo_id) REFERENCES processos (id), 
	FOREIGN KEY(municipio_origem_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_origem_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_origem_id) REFERENCES unidades (id), 
	FOREIGN KEY(municipio_destino_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_destino_id) REFERENCES orgaos (id), 
	FOREIGN KEY(unidade_destino_id) REFERENCES unidades (id), 
	FOREIGN KEY(created_by) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_tramites_id ON tramites (id);

-- movements
CREATE TABLE IF NOT EXISTS movements (
	id SERIAL NOT NULL, 
	product_id INTEGER, 
	item_id INTEGER, 
	unit_origem_id INTEGER, 
	unit_destino_id INTEGER, 
	quantidade INTEGER, 
	tipo VARCHAR(30) NOT NULL, 
	data TIMESTAMP WITHOUT TIME ZONE, 
	observacao TEXT, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(product_id) REFERENCES products (id), 
	FOREIGN KEY(item_id) REFERENCES items (id), 
	FOREIGN KEY(unit_origem_id) REFERENCES unidades (id), 
	FOREIGN KEY(unit_destino_id) REFERENCES unidades (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

-- paiol_itens
CREATE TABLE IF NOT EXISTS paiol_itens (
	id SERIAL NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	deposito_id INTEGER NOT NULL, 
	localizacao_id INTEGER, 
	num_serie VARCHAR(100), 
	tombo VARCHAR(100), 
	status VARCHAR(50), 
	observacao TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(localizacao_id) REFERENCES paiol_localizacoes (id), 
	UNIQUE (num_serie)
);

CREATE INDEX IF NOT EXISTS ix_paiol_itens_id ON paiol_itens (id);

-- paiol_requisicao_itens
CREATE TABLE IF NOT EXISTS paiol_requisicao_itens (
	id SERIAL NOT NULL, 
	requisicao_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	quantidade_solicitada INTEGER NOT NULL, 
	quantidade_atendida INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(requisicao_id) REFERENCES paiol_requisicoes (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_requisicao_itens_id ON paiol_requisicao_itens (id);

-- paiol_saldos
CREATE TABLE IF NOT EXISTS paiol_saldos (
	id SERIAL NOT NULL, 
	municipio_id INTEGER NOT NULL, 
	orgao_id INTEGER NOT NULL, 
	material_id INTEGER NOT NULL, 
	deposito_id INTEGER NOT NULL, 
	localizacao_id INTEGER, 
	lote_id INTEGER, 
	quantidade INTEGER, 
	quantidade_minima INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(municipio_id) REFERENCES municipios (id), 
	FOREIGN KEY(orgao_id) REFERENCES orgaos (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(localizacao_id) REFERENCES paiol_localizacoes (id), 
	FOREIGN KEY(lote_id) REFERENCES paiol_lotes (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_saldos_id ON paiol_saldos (id);

-- paiol_custodia_eventos
CREATE TABLE IF NOT EXISTS paiol_custodia_eventos (
	id SERIAL NOT NULL, 
	evento VARCHAR(50) NOT NULL, 
	material_id INTEGER, 
	item_id INTEGER, 
	deposito_id INTEGER, 
	documento_ref VARCHAR(100), 
	user_id INTEGER NOT NULL, 
	detalhes TEXT, 
	created_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id), 
	FOREIGN KEY(item_id) REFERENCES paiol_itens (id), 
	FOREIGN KEY(deposito_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_custodia_eventos_id ON paiol_custodia_eventos (id);

-- paiol_movimentacoes
CREATE TABLE IF NOT EXISTS paiol_movimentacoes (
	id SERIAL NOT NULL, 
	material_id INTEGER, 
	item_id INTEGER, 
	requisicao_id INTEGER, 
	deposito_origem_id INTEGER, 
	deposito_destino_id INTEGER, 
	quantidade INTEGER, 
	tipo VARCHAR(40) NOT NULL, 
	status VARCHAR(30), 
	data TIMESTAMP WITHOUT TIME ZONE, 
	observacao TEXT, 
	user_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(material_id) REFERENCES paiol_materiais (id), 
	FOREIGN KEY(item_id) REFERENCES paiol_itens (id), 
	FOREIGN KEY(requisicao_id) REFERENCES paiol_requisicoes (id), 
	FOREIGN KEY(deposito_origem_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(deposito_destino_id) REFERENCES paiol_depositos (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE INDEX IF NOT EXISTS ix_paiol_movimentacoes_id ON paiol_movimentacoes (id);

-- Unique marcas (case-insensitive)
CREATE UNIQUE INDEX IF NOT EXISTS uq_brands_nome_lower ON brands (lower(btrim(nome)));

