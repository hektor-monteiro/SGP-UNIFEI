from django.db import models
import uuid

class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Instituicao(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sigla = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Instituição'
        verbose_name_plural = 'Instituições'
        ordering = ['sigla']

    def __str__(self):
        return f'{self.sigla} - {self.nome}'

class Fomentador(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sigla = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=10, choices=[
        ('bolsa', 'Bolsa'),
        ('projeto', 'Projeto'),
    ])
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Fomentador'
        verbose_name_plural = 'Fomentadores'
        ordering = ['sigla']

    def __str__(self):
        return f'{self.sigla} - {self.nome}'

class ProcessoSipac(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=30, unique=True)
    descricao = models.TextField(blank=True)
    data_abertura = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'Processo SIPAC'
        verbose_name_plural = 'Processos SIPAC'
        ordering = ['numero']

    def __str__(self):
        return self.numero

class Perfil(TimeStampedModel):
    """Vincula um usuário Django a um perfil de acesso e, opcionalmente, a uma Pessoa.

    Hierarquia de permissões (crescente):
    aluno < docente < tecnico < diretor < proreitor
    """
    PERFIL_ALUNO = 'aluno'
    PERFIL_DOCENTE = 'docente'
    PERFIL_TECNICO = 'tecnico'
    PERFIL_DIRETOR = 'diretor'
    PERFIL_PROREITOR = 'proreitor'

    PERFIS = [
        (PERFIL_ALUNO, 'Aluno'),
        (PERFIL_DOCENTE, 'Docente'),
        (PERFIL_TECNICO, 'Técnico Administrativo'),
        (PERFIL_DIRETOR, 'Diretor de Pesquisa'),
        (PERFIL_PROREITOR, 'Pro-reitor de Pesquisa e Inovação'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='perfil',
        verbose_name='Usuário',
    )
    pessoa = models.OneToOneField(
        'projetos.Pessoa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil',
        verbose_name='Pessoa',
    )
    perfil = models.CharField(max_length=15, choices=PERFIS, default=PERFIL_ALUNO)

    # LGPD (§6): consentimento explícito para coleta de dados
    consentimento_lgpd = models.BooleanField(
        default=False,
        verbose_name='Consentimento LGPD',
    )
    data_consentimento = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Data do consentimento',
    )

    class Meta:
        verbose_name = 'Perfil'
        verbose_name_plural = 'Perfis'
        ordering = ['perfil', 'user__username']

    def __str__(self):
        return f'{self.user.username} ({self.get_perfil_display()})'

    @property
    def nivel(self) -> int:
        """Nível hierárquico do perfil (maior = mais permissão)."""
        ordem = {
            self.PERFIL_ALUNO: 1,
            self.PERFIL_DOCENTE: 2,
            self.PERFIL_TECNICO: 3,
            self.PERFIL_DIRETOR: 4,
            self.PERFIL_PROREITOR: 5,
        }
        return ordem.get(self.perfil, 0)

    def tem_perfil(self, *perfis) -> bool:
        """Verifica se o usuário possui algum dos perfis informados."""
        return self.perfil in perfis

    def pelo_menos(self, perfil: str) -> bool:
        """Verifica se o usuário possui nível hierárquico igual ou superior."""
        ordem = {
            self.PERFIL_ALUNO: 1,
            self.PERFIL_DOCENTE: 2,
            self.PERFIL_TECNICO: 3,
            self.PERFIL_DIRETOR: 4,
            self.PERFIL_PROREITOR: 5,
        }
        return self.nivel >= ordem.get(perfil, 99)


class LogAuditoria(TimeStampedModel):
    """Log de auditoria LGPD: quem acessou o quê e quando (§6).

    Registrado por `AuditoriaMiddleware` (escritas, exclusões e acessos
    negados) e por sinais de autenticação (login/logout). Leituras comuns
    (GET) não são registradas para evitar ruído excessivo.
    """
    ACOES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('escrita', 'Criação/Alteração'),
        ('exclusao', 'Exclusão'),
        ('acesso_negado', 'Acesso negado'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs_auditoria',
        verbose_name='Usuário',
    )
    acao = models.CharField(max_length=15, choices=ACOES)
    caminho = models.CharField(max_length=200)
    view = models.CharField(max_length=200, blank=True)
    metodo = models.CharField(max_length=10)
    status = models.PositiveSmallIntegerField(null=True, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-criado_em']

    def __str__(self):
        quem = self.usuario.username if self.usuario else 'anônimo'
        return f'{self.get_acao_display()} — {quem} — {self.caminho}'


class SolicitacaoLGPD(TimeStampedModel):
    """Solicitação de titular de dados (§6): correção ou exclusão/anonimização.

    O titular abre a solicitação; técnicos+ (encarregado/DPO) tratam,
    podendo concluir a exclusão executando a anonimização dos dados
    pessoais, preservando os registros de pesquisa e prestação de contas.
    """
    TIPO_CORRECAO = 'correcao'
    TIPO_EXCLUSAO = 'exclusao'
    TIPOS = [
        (TIPO_CORRECAO, 'Correção de dados'),
        (TIPO_EXCLUSAO, 'Exclusão (anonimização)'),
    ]

    STATUS_ABERTA = 'aberta'
    STATUS_EM_ANALISE = 'em_analise'
    STATUS_CONCLUIDA = 'concluida'
    STATUS_INDEFERIDA = 'indeferida'
    STATUS = [
        (STATUS_ABERTA, 'Aberta'),
        (STATUS_EM_ANALISE, 'Em análise'),
        (STATUS_CONCLUIDA, 'Concluída'),
        (STATUS_INDEFERIDA, 'Indeferida'),
    ]
    STATUS_FINAL = (STATUS_CONCLUIDA, STATUS_INDEFERIDA)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titular = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='solicitacoes_lgpd',
        verbose_name='Titular',
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    descricao = models.TextField(
        verbose_name='Descrição',
        help_text='Que dados devem ser corrigidos ou por que solicita a exclusão.',
    )
    status = models.CharField(
        max_length=10, choices=STATUS, default=STATUS_ABERTA,
    )
    justificativa = models.TextField(
        blank=True,
        verbose_name='Justificativa do encarregado',
    )
    tratado_por = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitacoes_lgpd_tratadas',
        verbose_name='Tratada por',
    )
    tratado_em = models.DateTimeField(
        null=True, blank=True, verbose_name='Tratada em',
    )

    class Meta:
        verbose_name = 'Solicitação LGPD'
        verbose_name_plural = 'Solicitações LGPD'
        ordering = ['-criado_em']

    def __str__(self):
        return (
            f'{self.get_tipo_display()} — {self.titular.username} '
            f'({self.get_status_display()})'
        )

    @property
    def esta_final(self) -> bool:
        """True quando a solicitação já foi concluída ou indeferida."""
        return self.status in self.STATUS_FINAL
