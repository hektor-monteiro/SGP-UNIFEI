from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
import re
import uuid
from apps.core.models import TimeStampedModel, Instituicao, Fomentador, ProcessoSipac

class Pessoa(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    cpf = models.CharField(max_length=14, blank=True)
    matricula = models.CharField(max_length=20, blank=True, null=True, unique=True)
    tipo = models.CharField(max_length=10, choices=[
        ('aluno', 'Aluno'),
        ('docente', 'Docente'),
        ('tecnico', 'Técnico'),
        ('externo', 'Externo'),
    ])
    instituicao = models.ForeignKey(Instituicao, on_delete=models.SET_NULL, null=True, blank=True)
    lattes = models.URLField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Pessoa'
        verbose_name_plural = 'Pessoas'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class ODS(TimeStampedModel):
    """Objetivo de Desenvolvimento Sustentável (ONU, agenda 2030)."""

    numero = models.PositiveSmallIntegerField(unique=True, verbose_name='número')
    nome = models.CharField(max_length=120)

    class Meta:
        verbose_name = 'ODS'
        verbose_name_plural = 'ODS'
        ordering = ['numero']

    def __str__(self):
        return f'ODS {self.numero} - {self.nome}'


class GrandeAreaConhecimento(TimeStampedModel):
    """Grande Área da tabela de Áreas do Conhecimento do CNPq."""

    codigo = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=150)

    class Meta:
        verbose_name = 'Grande Área de Conhecimento'
        verbose_name_plural = 'Grandes Áreas de Conhecimento'
        ordering = ['codigo']

    def __str__(self):
        return self.nome


class AreaConhecimento(TimeStampedModel):
    """Área da tabela de Áreas do Conhecimento do CNPq."""

    codigo = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=150)
    grande_area = models.ForeignKey(
        GrandeAreaConhecimento, on_delete=models.CASCADE, related_name='areas',
    )

    class Meta:
        verbose_name = 'Área de Conhecimento'
        verbose_name_plural = 'Áreas de Conhecimento'
        ordering = ['codigo']

    def __str__(self):
        return self.nome


class SubareaConhecimento(TimeStampedModel):
    """Subárea da tabela de Áreas do Conhecimento do CNPq."""

    codigo = models.CharField(max_length=10, unique=True)
    nome = models.CharField(max_length=150)
    area = models.ForeignKey(
        AreaConhecimento, on_delete=models.CASCADE, related_name='subareas',
    )

    class Meta:
        verbose_name = 'Subárea de Conhecimento'
        verbose_name_plural = 'Subáreas de Conhecimento'
        ordering = ['codigo']

    def __str__(self):
        return self.nome


class Projeto(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50, unique=True)
    titulo = models.CharField(max_length=500)
    descricao = models.TextField(blank=True)
    data_registro = models.DateField()
    data_inicio = models.DateField()
    data_termino = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=[
        ('vigente', 'Vigente'),
        ('expirado', 'Expirado'),
        ('cancelado', 'Cancelado'),
        ('arquivado', 'Arquivado'),
        ('concluido', 'Concluído'),
    ], default='vigente')
    # Avaliação por pares (§3.4): separada do ciclo de vida do projeto
    # (status acima). O coordenador envia para avaliação; o técnico aloca
    # docentes; a nota final alimenta a alocação de bolsas como indicador.
    status_avaliacao = models.CharField(
        max_length=15,
        choices=[
            ('nao_submetido', 'Não submetido'),
            ('submetido', 'Submetido'),
            ('em_avaliacao', 'Em avaliação'),
            ('avaliada', 'Avaliada'),
        ],
        default='nao_submetido',
        verbose_name='Status da avaliação',
    )
    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Nota da avaliação por pares',
        help_text='Média das notas das avaliações concluídas.',
    )
    fomentador = models.ForeignKey(Fomentador, on_delete=models.SET_NULL, null=True, blank=True, related_name='projetos')
    recursos_internos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    recursos_externos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    coordenador = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True, blank=True, related_name='projetos_coordenados')
    processo_sipac = models.ForeignKey(ProcessoSipac, on_delete=models.SET_NULL, null=True, blank=True)
    instituicao = models.ForeignKey(Instituicao, on_delete=models.SET_NULL, null=True, blank=True)
    # Ficha ODS + Área do Conhecimento (obrigatórios no formulário; nulos no
    # model por compatibilidade com registros anteriores a esta migração)
    ods = models.ManyToManyField(
        ODS, blank=True, related_name='projetos', verbose_name='ODS',
    )
    grande_area = models.ForeignKey(
        GrandeAreaConhecimento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projetos', verbose_name='Grande Área',
    )
    area = models.ForeignKey(
        AreaConhecimento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projetos',
    )
    subarea = models.ForeignKey(
        SubareaConhecimento, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projetos', verbose_name='Subárea',
    )

    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-data_registro']

    def __str__(self):
        return f'{self.codigo} - {self.titulo[:50]}'


# Padrão dos códigos existentes na DIP: PVDI + sequencial + ano de registro
PADRAO_CODIGO_PROJETO = re.compile(r'^PVDI(\d+)-(\d{4})$')


def gerar_codigo_projeto(data_referencia=None) -> str:
    """Gera o próximo código de projeto no padrão PVDI###-AAAA.

    O número é o maior sequencial já usado no padrão (qualquer ano) mais 1,
    com mínimo de 3 dígitos; o ano é o da data de registro informada ou da
    data corrente. A unicidade também é garantida pelo banco
    (`Projeto.codigo` é único) — a janela de corrida entre a validação e o
    INSERT é coberta pela constraint.
    """
    maior_numero = 0
    for codigo in Projeto.objects.values_list('codigo', flat=True):
        correspondencia = PADRAO_CODIGO_PROJETO.match(codigo)
        if correspondencia:
            maior_numero = max(maior_numero, int(correspondencia.group(1)))
    data = data_referencia or timezone.localdate()
    return f'PVDI{maior_numero + 1:03d}-{data.year}'


class Proposta(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.CharField(max_length=500)
    resumo = models.TextField(blank=True)
    edital = models.ForeignKey(
        'editais.Edital',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='propostas',
        verbose_name='Edital',
    )
    projeto = models.ForeignKey(
        Projeto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='propostas',
        verbose_name='Projeto',
        help_text='Projeto que solicita as cotas de bolsa.',
    )
    cotas = models.PositiveIntegerField(
        default=1,
        verbose_name='Cotas solicitadas',
        help_text='Quantidade de cotas de bolsa solicitadas para o projeto.',
        validators=[MinValueValidator(1)],
    )
    submetido_por = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='propostas')
    data_submissao = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=15, choices=[
        ('submetida', 'Submetida'),
        ('em_avaliacao', 'Em Avaliação'),
        ('aprovada', 'Aprovada'),
        ('reprovada', 'Reprovada'),
        ('desclassificada', 'Desclassificada'),
    ], default='submetida')
    nota_final = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Proposta'
        verbose_name_plural = 'Propostas'
        ordering = ['-data_submissao']

    def __str__(self):
        return self.titulo[:50]
