from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Float, Date, ForeignKey, func, Enum as SQLEnum, Table, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from database import Base
from datetime import datetime
import enum


def _agora_brasilia():
    """Horário de Brasília (import diferido para evitar ciclo com dependencies)."""
    from dependencies import agora_brasilia
    return agora_brasilia()


# =====================================================
# ENUMS
# =====================================================

class PerfilEnum(enum.Enum):
    MASTER = "master"
    ADMIN_MUNICIPAL = "admin_municipal"
    GESTOR_ESTOQUE = "gestor_estoque"
    GESTOR_PROTOCOLO = "gestor_protocolo"
    GESTOR_GERAL = "gestor_geral"
    GESTOR_SEGEM = "gestor_segem"
    OPERADOR = "operador"


class StatusUsuarioEnum(enum.Enum):
    ATIVO = "ativo"
    INATIVO = "inativo"
    BLOQUEADO = "bloqueado"
    PENDENTE = "pendente"  # aguardando aprovação


# =====================================================
# USER - REFATORADO
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    nome = Column(String(200), nullable=False)  # ✅ nome completo
    cpf = Column(String(11), unique=True, nullable=False, index=True)  # ✅ só números
    email = Column(String(200), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)  # ✅ use bcrypt para hash
    
    # ✅ Hierarquia administrativa
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    # ✅ Perfil e Status (coluna no banco: role / status)
    perfil = Column(
        "role",
        SQLEnum(PerfilEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=PerfilEnum.OPERADOR,
    )
    status = Column(
        SQLEnum(StatusUsuarioEnum, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=StatusUsuarioEnum.PENDENTE,
    )
    
    # ✅ Auditoria
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))  # quem criou
    ultimo_acesso = Column(DateTime)
    
    # Relacionamentos
    municipio = relationship("Municipio", back_populates="users")
    orgao = relationship("Orgao")
    unidade = relationship("Unidade")
    movements = relationship("Movement", back_populates="user")

    # Alias legado: sessão e routers antigos usam "username" (= e-mail)
    @hybrid_property
    def username(self):
        return self.email

    @username.setter
    def username(self, value):
        self.email = value

    @username.expression
    def username(cls):
        return cls.email

    @property
    def role(self):
        p = self.perfil
        return p.value if hasattr(p, "value") else p

    @role.setter
    def role(self, value):
        self.perfil = PerfilEnum(value) if isinstance(value, str) else value

    def __str__(self):
        return f"{self.nome} ({self.cpf})"
    
    # ✅ Métodos helper para permissões (usam strings)
    def _perfil_valor(self):
        p = self.perfil
        return p.value if hasattr(p, "value") else str(p)

    def pode_acessar_inventario(self):
        return self._perfil_valor() in {
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
            PerfilEnum.GESTOR_ESTOQUE.value,
            PerfilEnum.GESTOR_GERAL.value,
            PerfilEnum.GESTOR_SEGEM.value,
        }
    
    def pode_acessar_protocolo(self):
        return self._perfil_valor() in {
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
            PerfilEnum.GESTOR_PROTOCOLO.value,
            PerfilEnum.GESTOR_GERAL.value,
        }

    def pode_acessar_segem(self):
        return self._perfil_valor() in {
            PerfilEnum.MASTER.value,
            PerfilEnum.GESTOR_SEGEM.value,
        }

    def pode_gerenciar_usuarios(self):
        return self._perfil_valor() in {
            PerfilEnum.MASTER.value,
            PerfilEnum.ADMIN_MUNICIPAL.value,
        }


# =====================================================
# UNIT (LEGADO)
# =====================================================

class Unit(Base):
    __tablename__ = "units"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), unique=True, nullable=False)
    manager = Column(String(100), nullable=False)

    def __str__(self):
        return self.name


# =====================================================
# PRODUCT - ADICIONAR municipio_id
# =====================================================

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    
    # ✅ ISOLAMENTO POR MUNICÍPIO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)  # ✅ rastreamento

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    type_id = Column(Integer, ForeignKey("equipment_types.id"), nullable=False)
    brand_id = Column(Integer, ForeignKey("brands.id"), nullable=False)

    model = Column(String)
    description = Column(Text)
    controla_por_serie = Column(Boolean, default=True)
    ativo = Column(Boolean, default=True)

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    
    # ✅ Auditoria
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    # RELACIONAMENTOS
    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    category = relationship("Category", back_populates="products")
    type = relationship("EquipmentType")
    brand = relationship("Brand")
    items = relationship("Item", back_populates="product", cascade="all, delete-orphan")
    stocks = relationship("Stock", back_populates="product", cascade="all, delete-orphan")
    attachments = relationship(
        "ProductAttachment",
        back_populates="product",
        cascade="all, delete-orphan",
    )


class ProductAttachment(Base):
    __tablename__ = "product_attachments"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    product = relationship("Product", back_populates="attachments")


# =====================================================
# ITEM (Produto com série = 1 item = 1 unidade física)
# =====================================================

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    
    # ✅ ISOLAMENTO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)

    tombo = Column(Boolean, default=False)
    num_tombo_ou_serie = Column(String, unique=True)

    estado_id = Column(Integer, ForeignKey("equipment_states.id"))
    status = Column(String, default="Disponível")

    data_aquisicao = Column(Date)
    valor_aquisicao = Column(Float)
    garantia_ate = Column(Date)
    observacao = Column(Text)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    product = relationship("Product", back_populates="items")
    estado = relationship("EquipmentState")
    unit = relationship("Unidade", back_populates="items")


# =====================================================
# STOCK (Produto sem série)
# =====================================================

class Stock(Base):
    __tablename__ = "stock"

    id = Column(Integer, primary_key=True)
    
    # ✅ ISOLAMENTO
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    unit_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)  # ✅ agora é Unidade

    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)
    localizacao = Column(String)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    product = relationship("Product", back_populates="stocks")
    unit = relationship("Unidade", back_populates="stocks")


# =====================================================
# MOVEMENT
# =====================================================

class Movement(Base):
    __tablename__ = "movements"

    id = Column(Integer, primary_key=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)

    unit_origem_id = Column(Integer, ForeignKey("unidades.id"))
    unit_destino_id = Column(Integer, ForeignKey("unidades.id"))

    quantidade = Column(Integer, default=1)
    tipo = Column(String(30), nullable=False)

    data = Column(DateTime, default=_agora_brasilia)
    observacao = Column(Text)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # RELACIONAMENTOS
    product = relationship("Product")
    item = relationship("Item")
    user = relationship("User", back_populates="movements")

    unit_origem = relationship(
        "Unidade",
        foreign_keys=[unit_origem_id],
        back_populates="movimentos_origem",
    )
    unit_destino = relationship(
        "Unidade",
        foreign_keys=[unit_destino_id],
        back_populates="movimentos_destino",
    )


# =====================================================
# LOG
# =====================================================

class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(50))
    acao = Column(String(255))
    ip = Column(String(50))
    data_hora = Column(DateTime(timezone=True), server_default=func.now())
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=True)
    user_agent = Column(String(500), nullable=True)
    tipo = Column(String(20), nullable=False, server_default="operacional", default="operacional")

    user = relationship("User", foreign_keys=[user_id])


# =====================================================
# EQUIPMENT TYPE
# =====================================================

class EquipmentType(Base):
    __tablename__ = "equipment_types"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)

    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    category = relationship("Category", backref="equipment_types")


# =====================================================
# CATEGORY
# =====================================================

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    descricao = Column(Text)
    ativo = Column(Boolean, default=True)

    products = relationship("Product", back_populates="category")

    def __str__(self):
        return self.nome


# =====================================================
# BRAND
# =====================================================

brand_equipment_types = Table(
    "brand_equipment_types",
    Base.metadata,
    Column("brand_id", Integer, ForeignKey("brands.id", ondelete="CASCADE"), primary_key=True),
    Column("type_id", Integer, ForeignKey("equipment_types.id", ondelete="CASCADE"), primary_key=True),
)


class Brand(Base):
    __tablename__ = "brands"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)

    equipment_types = relationship(
        "EquipmentType",
        secondary=brand_equipment_types,
        backref="brands",
    )


# =====================================================
# EQUIPMENT STATE
# =====================================================

class EquipmentState(Base):
    __tablename__ = "equipment_states"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, nullable=False)

# =====================================================
# E-PROTOCOLO - CROSS-MUNICIPAL
# =====================================================

class Processo(Base):
    __tablename__ = "processos"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(50), unique=True, index=True)
    ano = Column(Integer)
    assunto = Column(String(500))
    requerente = Column(String(200))
    conteudo = Column(Text)
    
    # ✅ Origem (quem criou)
    municipio_origem_id = Column(Integer, ForeignKey("municipios.id"), nullable=True)
    orgao_origem_id = Column(Integer, ForeignKey("orgaos.id"), nullable=True)
    unidade_origem_id = Column(Integer, ForeignKey("unidades.id"), nullable=True)
    
    # ✅ Localização atual (onde está agora)
    municipio_atual_id = Column(Integer, ForeignKey("municipios.id"), nullable=True)
    orgao_atual_id = Column(Integer, ForeignKey("orgaos.id"), nullable=True)
    unidade_atual_id = Column(Integer, ForeignKey("unidades.id"), nullable=True)
    
    # Status: Em tramitação | Recebido | Em edição | Assinado
    status = Column(String(50), default="Em tramitação")
    urgente = Column(Boolean, default=False)
    nivel_acesso = Column(String(20), default="Público")  # Público/Restrito
    
    # Controle de leitura (aba "Lidos" / "Não lidos")
    lido_at = Column(DateTime, nullable=True)
    # Atribuição (aba "Não atribuídos" / "Atribuídos")
    atribuido_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    # Apensamento: quando preenchido, este processo está apensado ao processo principal
    processo_principal_id = Column(Integer, ForeignKey("processos.id"), nullable=True)
    
    # Arquivamento
    arquivado = Column(Boolean, default=False)
    arquivado_at = Column(DateTime, nullable=True)
    arquivado_por_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    # Relacionamentos
    atribuido_to = relationship("User", foreign_keys=[atribuido_to_id])
    processo_principal = relationship("Processo", remote_side="Processo.id", foreign_keys=[processo_principal_id], back_populates="apensos")
    apensos = relationship("Processo", back_populates="processo_principal", foreign_keys=[processo_principal_id])
    municipio_origem = relationship("Municipio", foreign_keys=[municipio_origem_id])
    municipio_atual = relationship("Municipio", foreign_keys=[municipio_atual_id])
    orgao_origem = relationship("Orgao", foreign_keys=[orgao_origem_id])
    orgao_atual = relationship("Orgao", foreign_keys=[orgao_atual_id])
    unidade_origem = relationship("Unidade", foreign_keys=[unidade_origem_id])
    unidade_atual = relationship("Unidade", foreign_keys=[unidade_atual_id])
    
    tramites = relationship("Tramite", back_populates="processo")
    assinantes = relationship("ProcessoAssinante", back_populates="processo")
    creator = relationship("User", foreign_keys=[created_by])
    arquivado_por = relationship("User", foreign_keys=[arquivado_por_id])


class ProcessoAssinante(Base):
    """Assinantes do processo (usuários que devem assinar)"""
    __tablename__ = "processo_assinantes"

    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    processo = relationship("Processo", back_populates="assinantes")
    user = relationship("User")


class Tramite(Base):
    """Histórico de movimentação do processo"""
    __tablename__ = "tramites"
    
    id = Column(Integer, primary_key=True, index=True)
    processo_id = Column(Integer, ForeignKey("processos.id"), nullable=False)
    
    # De onde saiu
    municipio_origem_id = Column(Integer, ForeignKey("municipios.id"))
    orgao_origem_id = Column(Integer, ForeignKey("orgaos.id"))
    unidade_origem_id = Column(Integer, ForeignKey("unidades.id"))
    
    # Para onde foi
    municipio_destino_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_destino_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_destino_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    despacho = Column(Text)
    anexo_path = Column(String(500))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    processo = relationship("Processo", back_populates="tramites")
    usuario = relationship("User")
    orgao_origem = relationship("Orgao", foreign_keys=[orgao_origem_id])
    unidade_origem = relationship("Unidade", foreign_keys=[unidade_origem_id])
    orgao_destino = relationship("Orgao", foreign_keys=[orgao_destino_id])
    unidade_destino = relationship("Unidade", foreign_keys=[unidade_destino_id])


class Circular(Base):
    __tablename__ = "circulares"
    
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(50), unique=True)
    assunto = Column(String(500))
    conteudo = Column(Text)
    
    # Remetente
    municipio_remetente_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_remetente_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_remetente_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))
    
    destinatarios = relationship("CircularDestinatario", back_populates="circular")


class CircularDestinatario(Base):
    """Destinatários de uma circular (múltiplos)"""
    __tablename__ = "circular_destinatarios"
    
    id = Column(Integer, primary_key=True, index=True)
    circular_id = Column(Integer, ForeignKey("circulares.id"), nullable=False)
    
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    
    recebido = Column(Boolean, default=False)
    data_recebimento = Column(DateTime)
    arquivado = Column(Boolean, default=False)
    
    circular = relationship("Circular", back_populates="destinatarios")


class Requerente(Base):
    """Requerentes para processos do E-Protocolo"""
    __tablename__ = "requerentes"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    tipo_documento = Column(String(20), nullable=False)  # CPF, CNPJ, RG
    numero_documento = Column(String(20), nullable=False)
    email = Column(String(200))
    cep = Column(String(10), nullable=False)
    endereco = Column(String(300), nullable=False)
    numero_endereco = Column(String(20), nullable=False)
    bairro = Column(String(100), nullable=False)
    complemento = Column(String(100))
    cidade = Column(String(200), nullable=False)
    uf = Column(String(2), nullable=False)
    telefone1 = Column(String(20))
    telefone2 = Column(String(20))
    
    created_at = Column(DateTime, default=datetime.utcnow)


# =====================================================
# CATEGORIA (GRUPO > ASSUNTO > SUBASSUNTO)
# =====================================================

class Grupo(Base):
    """Grupo de categorização (nível superior)"""
    __tablename__ = "grupos"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    assuntos = relationship("Assunto", back_populates="grupo")


class Assunto(Base):
    """Assunto vinculado a um Grupo"""
    __tablename__ = "assuntos"
    
    id = Column(Integer, primary_key=True, index=True)
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    grupo = relationship("Grupo", back_populates="assuntos")
    subassuntos = relationship("Subassunto", back_populates="assunto")


class Subassunto(Base):
    """Subassunto vinculado a um Assunto"""
    __tablename__ = "subassuntos"
    
    id = Column(Integer, primary_key=True, index=True)
    assunto_id = Column(Integer, ForeignKey("assuntos.id"), nullable=False)
    nome = Column(String(200), nullable=False)
    ativo = Column(Boolean, default=True)
    
    assunto = relationship("Assunto", back_populates="subassuntos")


# =====================================================
# HIERARQUIA GEOGRÁFICA/ADMINISTRATIVA
# =====================================================

class Estado(Base):
    __tablename__ = "estados"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), unique=True, nullable=False)
    uf = Column(String(2), unique=True, nullable=False)
    
    municipios = relationship("Municipio", back_populates="estado")


class Municipio(Base):
    __tablename__ = "municipios"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    codigo_ibge = Column(String(7), unique=True)  # ✅ código IBGE para validação
    estado_id = Column(Integer, ForeignKey("estados.id"), nullable=False)
    ativo = Column(Boolean, default=True)
    
    estado = relationship("Estado", back_populates="municipios")
    orgaos = relationship("Orgao", back_populates="municipio")
    users = relationship("User", back_populates="municipio")


class Orgao(Base):
    """Secretarias/Órgãos dentro de um município"""
    __tablename__ = "orgaos"
    
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)  # Ex: "Secretaria de Saúde"
    sigla = Column(String(20))  # Ex: "SESAU"
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    responsavel = Column(String(200))  # ✅ nome do responsável
    email = Column(String(200))  # ✅ email institucional
    telefone = Column(String(20))
    ativo = Column(Boolean, default=True)
    
    municipio = relationship("Municipio", back_populates="orgaos")
    unidades = relationship("Unidade", back_populates="orgao")


class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    sigla = Column(String(20))
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    responsavel = Column(String(200))
    ramal = Column(String(10))
    ativo = Column(Boolean, default=True)

    orgao = relationship("Orgao", back_populates="unidades")

    # Compatibilidade com routers/templates legados (name/manager)
    @hybrid_property
    def name(self):
        return self.nome

    @name.setter
    def name(self, value):
        self.nome = value

    @name.expression
    def name(cls):
        return cls.nome

    @hybrid_property
    def manager(self):
        return self.responsavel

    @manager.setter
    def manager(self, value):
        self.responsavel = value

    @manager.expression
    def manager(cls):
        return cls.responsavel

    users = relationship("User", back_populates="unidade")
    items = relationship("Item", back_populates="unit")
    stocks = relationship("Stock", back_populates="unit")
    movimentos_origem = relationship(
        "Movement",
        foreign_keys="Movement.unit_origem_id",
        back_populates="unit_origem",
        overlaps="unit_origem",
    )
    movimentos_destino = relationship(
        "Movement",
        foreign_keys="Movement.unit_destino_id",
        back_populates="unit_destino",
        overlaps="unit_destino",
    )


# =====================================================
# SEGEM (Sistema de Gestão de Materiais)
# =====================================================

class SegemItem(Base):
    __tablename__ = "segem_itens"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)

    ano = Column(Integer)  # ANO
    num_tombo_gcm = Column(String(50))  # Nº TOMBO (GCM)
    local = Column(String(200))  # LOCAL
    codigo = Column(String(100))  # CÓDIGO
    descricao = Column(Text)  # DESCRIÇÃO
    situacao = Column(String(100))  # SITUAÇÃO
    valor_rs = Column(Float)  # VALOR R$
    entrada_no_siga = Column(String(100))  # ENTRADA NO SIGA
    nota_de_empenho = Column(String(100))  # NOTA DE EMPENHO
    valor_nota_empenho = Column(Float)  # VALOR DA NOTA DE EMPENHO
    num_nota_fiscal = Column(String(100))  # N° NOTA FISCAL
    nome_empresa = Column(String(200))  # NOME DA EMPRESA
    classificacao_asi = Column(String(100))  # CLASSIFICAÇÃO ASI

    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    produtos = relationship("SegemItemProduto", back_populates="segem_item", cascade="all, delete-orphan")


class SegemItemProduto(Base):
    """Produtos adicionais do registro SEGEM (Nº Tombo + Valor), linha do bloco Produto."""
    __tablename__ = "segem_itens_produtos"

    id = Column(Integer, primary_key=True, index=True)
    segem_item_id = Column(Integer, ForeignKey("segem_itens.id"), nullable=False)
    num_tombo_gcm = Column(String(50))
    valor_rs = Column(Float)

    segem_item = relationship("SegemItem", back_populates="produtos")


class ProdutoSegem(Base):
    """Catálogo de produtos SEGEM (código + descrição) para preenchimento automático no formulário."""
    __tablename__ = "produtos_segem"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(100), unique=True, nullable=False, index=True)
    descricao = Column(Text)


# =====================================================
# PAIOL — Divisão de Material Bélico (tabelas isoladas)
# =====================================================

class PaiolClasseMaterial(Base):
    __tablename__ = "paiol_classes_material"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(30), unique=True, nullable=False)
    nome = Column(String(120), nullable=False)
    descricao = Column(Text)
    grupo_compatibilidade = Column(String(30))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    materiais = relationship("PaiolMaterial", back_populates="classe")


class PaiolFabricante(Base):
    __tablename__ = "paiol_fabricantes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False, unique=True)
    pais = Column(String(80))
    cnpj = Column(String(20))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    materiais = relationship("PaiolMaterial", back_populates="fabricante")


class PaiolFornecedor(Base):
    __tablename__ = "paiol_fornecedores"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(200), nullable=False)
    cnpj = Column(String(20))
    contato = Column(String(200))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaiolTipoMaterial(Base):
    __tablename__ = "paiol_tipos_material"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(40), unique=True, nullable=False)
    categoria = Column(String(50), nullable=False)
    especie = Column(String(200), nullable=False)
    descricao = Column(Text)
    detalhes = Column(JSON, nullable=True)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PaiolMunicao(Base):
    """Catálogo de munições."""
    __tablename__ = "paiol_municoes"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(40), unique=True, nullable=False)
    nome_comercial = Column(String(300), nullable=False)
    calibre = Column(String(80), nullable=False)
    fabricante_marca = Column(String(200))
    fabricante_id = Column(Integer, ForeignKey("paiol_fabricantes.id"), nullable=True)
    quantidade_tipo = Column(String(20))
    quantidade_valor = Column(Integer)
    descricao = Column(Text)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    fabricante = relationship("PaiolFabricante")


class PaiolDeposito(Base):
    __tablename__ = "paiol_depositos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(30), unique=True, nullable=False)
    nome = Column(String(200), nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=True)
    responsavel_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    endereco = Column(String(300))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    unidade = relationship("Unidade")
    responsavel = relationship("User", foreign_keys=[responsavel_id])
    localizacoes = relationship("PaiolLocalizacao", back_populates="deposito", cascade="all, delete-orphan")
    saldos = relationship("PaiolSaldo", back_populates="deposito")
    usuarios_autorizados = relationship("PaiolUsuarioAutorizado", back_populates="deposito")


class PaiolLocalizacao(Base):
    __tablename__ = "paiol_localizacoes"

    id = Column(Integer, primary_key=True, index=True)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=False)
    codigo = Column(String(50), nullable=False)
    descricao = Column(String(200))
    ativo = Column(Boolean, default=True)

    deposito = relationship("PaiolDeposito", back_populates="localizacoes")
    saldos = relationship("PaiolSaldo", back_populates="localizacao")


class PaiolMaterial(Base):
    __tablename__ = "paiol_materiais"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text)
    tipo = Column(String(30), nullable=False)
    calibre = Column(String(80))
    classe_id = Column(Integer, ForeignKey("paiol_classes_material.id"), nullable=True)
    fabricante_id = Column(Integer, ForeignKey("paiol_fabricantes.id"), nullable=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    controla_por_serie = Column(Boolean, default=True)
    controla_lote = Column(Boolean, default=False)
    quantidade_minima = Column(Integer, default=0)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"))

    classe = relationship("PaiolClasseMaterial", back_populates="materiais")
    fabricante = relationship("PaiolFabricante", back_populates="materiais")
    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    itens = relationship("PaiolItem", back_populates="material", cascade="all, delete-orphan")
    lotes = relationship("PaiolLote", back_populates="material", cascade="all, delete-orphan")
    saldos = relationship("PaiolSaldo", back_populates="material", cascade="all, delete-orphan")
    movimentacoes = relationship("PaiolMovimentacao", back_populates="material")


class PaiolLote(Base):
    __tablename__ = "paiol_lotes"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=False)
    numero_lote = Column(String(80), nullable=False)
    data_fabricacao = Column(Date)
    data_validade = Column(Date)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    material = relationship("PaiolMaterial", back_populates="lotes")
    saldos = relationship("PaiolSaldo", back_populates="lote")


class PaiolItem(Base):
    __tablename__ = "paiol_itens"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=False)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=False)
    localizacao_id = Column(Integer, ForeignKey("paiol_localizacoes.id"), nullable=True)
    num_serie = Column(String(100), unique=True)
    tombo = Column(String(100))
    status = Column(String(50), default="Disponível")
    observacao = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    material = relationship("PaiolMaterial", back_populates="itens")
    deposito = relationship("PaiolDeposito")
    localizacao = relationship("PaiolLocalizacao")
    movimentacoes = relationship("PaiolMovimentacao", back_populates="item")


class PaiolSaldo(Base):
    __tablename__ = "paiol_saldos"

    id = Column(Integer, primary_key=True, index=True)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=False)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=False)
    localizacao_id = Column(Integer, ForeignKey("paiol_localizacoes.id"), nullable=True)
    lote_id = Column(Integer, ForeignKey("paiol_lotes.id"), nullable=True)
    quantidade = Column(Integer, default=0)
    quantidade_minima = Column(Integer, default=0)

    municipio = relationship("Municipio")
    orgao = relationship("Orgao")
    material = relationship("PaiolMaterial", back_populates="saldos")
    deposito = relationship("PaiolDeposito", back_populates="saldos")
    localizacao = relationship("PaiolLocalizacao", back_populates="saldos")
    lote = relationship("PaiolLote", back_populates="saldos")


class PaiolMovimentacao(Base):
    __tablename__ = "paiol_movimentacoes"

    id = Column(Integer, primary_key=True, index=True)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("paiol_itens.id"), nullable=True)
    requisicao_id = Column(Integer, ForeignKey("paiol_requisicoes.id"), nullable=True)
    deposito_origem_id = Column(Integer, ForeignKey("paiol_depositos.id"))
    deposito_destino_id = Column(Integer, ForeignKey("paiol_depositos.id"))
    quantidade = Column(Integer, default=1)
    tipo = Column(String(40), nullable=False)
    status = Column(String(30), default="executado")
    data = Column(DateTime, default=datetime.utcnow)
    observacao = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    material = relationship("PaiolMaterial", back_populates="movimentacoes")
    item = relationship("PaiolItem", back_populates="movimentacoes")
    requisicao = relationship("PaiolRequisicao", back_populates="movimentacoes")
    user = relationship("User")
    deposito_origem = relationship("PaiolDeposito", foreign_keys=[deposito_origem_id])
    deposito_destino = relationship("PaiolDeposito", foreign_keys=[deposito_destino_id])


class PaiolUsuarioAutorizado(Base):
    __tablename__ = "paiol_usuarios_autorizados"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=True)
    classe_id = Column(Integer, ForeignKey("paiol_classes_material.id"), nullable=True)
    operacoes = Column(String(500))
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    deposito = relationship("PaiolDeposito", back_populates="usuarios_autorizados")
    classe = relationship("PaiolClasseMaterial")


class PaiolCustodiaEvento(Base):
    """Trilha imutável de custódia (append-only)."""
    __tablename__ = "paiol_custodia_eventos"

    id = Column(Integer, primary_key=True, index=True)
    evento = Column(String(50), nullable=False)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=True)
    item_id = Column(Integer, ForeignKey("paiol_itens.id"), nullable=True)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=True)
    documento_ref = Column(String(100))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    detalhes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    material = relationship("PaiolMaterial")
    deposito = relationship("PaiolDeposito")


class PaiolDashboardAtalho(Base):
    """Atalhos personalizados da dashboard por usuário."""
    __tablename__ = "paiol_dashboard_atalhos"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    menu_key = Column(String(80), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


class PaiolRequisicao(Base):
    """Solicitação de material bélico por unidade."""
    __tablename__ = "paiol_requisicoes"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(30), nullable=False, index=True)
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=False)
    municipio_id = Column(Integer, ForeignKey("municipios.id"), nullable=False)
    solicitante_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=True)
    deposito_id = Column(Integer, ForeignKey("paiol_depositos.id"), nullable=True)
    status = Column(String(30), default="rascunho", nullable=False)
    observacao = Column(Text)
    motivo_rejeicao = Column(Text)
    aprovador_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    aprovado_em = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    orgao = relationship("Orgao")
    municipio = relationship("Municipio")
    solicitante = relationship("User", foreign_keys=[solicitante_id])
    aprovador = relationship("User", foreign_keys=[aprovador_id])
    unidade = relationship("Unidade")
    deposito = relationship("PaiolDeposito")
    itens = relationship("PaiolRequisicaoItem", back_populates="requisicao", cascade="all, delete-orphan")
    movimentacoes = relationship("PaiolMovimentacao", back_populates="requisicao")


class PaiolRequisicaoItem(Base):
    __tablename__ = "paiol_requisicao_itens"

    id = Column(Integer, primary_key=True, index=True)
    requisicao_id = Column(Integer, ForeignKey("paiol_requisicoes.id"), nullable=False)
    material_id = Column(Integer, ForeignKey("paiol_materiais.id"), nullable=False)
    quantidade_solicitada = Column(Integer, nullable=False, default=1)
    quantidade_atendida = Column(Integer, nullable=False, default=0)

    requisicao = relationship("PaiolRequisicao", back_populates="itens")
    material = relationship("PaiolMaterial")


class PaiolAssinatura(Base):
    """Registro de assinatura em documentos críticos do paiol."""
    __tablename__ = "paiol_assinaturas"

    id = Column(Integer, primary_key=True, index=True)
    documento_tipo = Column(String(40), nullable=False)
    documento_id = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    hash_registro = Column(String(128), nullable=False)
    observacao = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")


# Alias legado: vários routers ainda importam Unit
Unit = Unidade
