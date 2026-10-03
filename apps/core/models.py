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
