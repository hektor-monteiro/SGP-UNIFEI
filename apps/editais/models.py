from django.db import models
import uuid
from apps.core.models import ModeloComArquivo, TimeStampedModel
from apps.core.validators import validar_pdf
from apps.bolsas.models import ModalidadeBolsa
from apps.projetos.models import Proposta

class Edital(TimeStampedModel, ModeloComArquivo):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50, unique=True)
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    # A redação completa do edital (objetivo, cronograma, requisitos,
    # habilitação...) fica no documento anexado abaixo — o técnico a
    # descreve no PDF, como no edital oficial da DiP. Obrigatório para
    # a aprovação/validação (diretor ou pro-reitor).
    arquivo_pdf = models.FileField(
        upload_to='uploads/editais/%Y/%m/',
        blank=True,
        validators=[validar_pdf],
        verbose_name='Documento (PDF)',
        help_text=(
            'Edital completo em PDF (até 15 MB). Obrigatório para '
            'aprovar e validar.'
        ),
    )
    campo_arquivo = 'arquivo_pdf'
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=15, choices=[
        ('rascunho', 'Rascunho'),
        ('aprovado', 'Aprovado'),
        ('em_andamento', 'Em Andamento'),
        ('encerrado', 'Encerrado'),
        ('cancelado', 'Cancelado'),
    ], default='rascunho')
    modalidade = models.ForeignKey(ModalidadeBolsa, on_delete=models.SET_NULL, null=True, blank=True)
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='editais_criados')
    validado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='editais_validados')
    data_validacao = models.DateTimeField(null=True, blank=True)
    nota_minima = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=6.00,
        verbose_name='Nota mínima para aprovação',
        help_text='Propostas com nota final igual ou superior são aprovadas automaticamente.',
    )

    class Meta:
        verbose_name = 'Edital'
        verbose_name_plural = 'Editais'
        ordering = ['-data_inicio']

    def __str__(self):
        return f'{self.codigo} - {self.titulo}'

class Avaliacao(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=10, choices=[
        ('proposta', 'Proposta'),
        ('relatorio', 'Relatório'),
        ('edital', 'Edital'),
        ('projeto', 'Projeto'),
    ])
    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, null=True, blank=True, related_name='avaliacoes')
    projeto = models.ForeignKey(
        'projetos.Projeto',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='avaliacoes',
        verbose_name='Projeto',
    )
    avaliador = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='avaliacoes')
    alocado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='alocacoes_realizadas')
    status = models.CharField(max_length=10, choices=[
        ('alocada', 'Alocada'),
        ('concluida', 'Concluída'),
    ], default='alocada')
    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Nota final (média ponderada)',
    )
    parecer = models.TextField(blank=True)
    data_avaliacao = models.DateTimeField(auto_now_add=True)
    data_conclusao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-data_avaliacao']

    def __str__(self):
        return f'{self.tipo} - {self.nota}'


class CriterioAvaliacao(TimeStampedModel):
    """Critério de avaliação com peso, adotado na média ponderada.

    Criado e editado por técnico+; os avaliadores dão notas de 0 a 10
    para cada critério ativo. O escopo separa os critérios usados na
    avaliação de propostas (editais) dos usados na avaliação por pares
    de projetos.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, unique=True)
    escopo = models.CharField(
        max_length=10,
        choices=[
            ('proposta', 'Propostas (editais)'),
            ('projeto', 'Projetos (avaliação por pares)'),
            ('ambos', 'Ambos'),
        ],
        default='proposta',
        verbose_name='Escopo',
    )
    descricao = models.TextField(blank=True)
    peso = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Peso',
        help_text='Peso do critério na média ponderada (maior que zero).',
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Critério de avaliação'
        verbose_name_plural = 'Critérios de avaliação'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} (peso {self.peso})'


class NotaCriterio(TimeStampedModel):
    """Nota de 0 a 10 dada por um avaliador para um critério específico."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    avaliacao = models.ForeignKey(Avaliacao, on_delete=models.CASCADE, related_name='notas')
    criterio = models.ForeignKey(CriterioAvaliacao, on_delete=models.CASCADE, related_name='notas')
    nota = models.DecimalField(max_digits=4, decimal_places=2)

    class Meta:
        verbose_name = 'Nota por critério'
        verbose_name_plural = 'Notas por critério'
        unique_together = ('avaliacao', 'criterio')
        ordering = ['criterio__nome']

    def __str__(self):
        return f'{self.criterio.nome}: {self.nota}'
