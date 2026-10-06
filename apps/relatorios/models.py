from django.db import models
import uuid
from apps.core.models import ModeloComArquivo, TimeStampedModel
from apps.core.validators import validar_pdf
from apps.projetos.models import Pessoa, Projeto
from apps.bolsas.models import Bolsa

class PlanoTrabalho(TimeStampedModel, ModeloComArquivo):
    """Plano de trabalho do aluno, associado à bolsa E ao projeto do docente.

    aluno e projeto são derivados da bolsa (formulário garante a coerência).
    O conteúdo completo fica no PDF anexado; no sistema ficam apenas os
    metadados e o `resumo` (texto curto que alimenta a busca).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bolsa = models.OneToOneField(Bolsa, on_delete=models.CASCADE, related_name='plano_trabalho')
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='planos_trabalho')
    aluno = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='planos_trabalho')
    titulo = models.CharField(max_length=255)
    resumo = models.TextField(
        max_length=1000,
        blank=True,
        verbose_name='Resumo',
        help_text=(
            'Texto curto (até 1000 caracteres) exibido na tela e usado '
            'na busca do sistema.'
        ),
    )
    arquivo_pdf = models.FileField(
        upload_to='uploads/planos/%Y/%m/',
        blank=True,
        validators=[validar_pdf],
        verbose_name='Documento (PDF)',
        help_text=(
            'Plano de trabalho completo em PDF (até 15 MB). Obrigatório '
            'para submeter (status diferente de Rascunho).'
        ),
    )
    campo_arquivo = 'arquivo_pdf'
    status = models.CharField(max_length=15, choices=[
        ('rascunho', 'Rascunho'),
        ('submetido', 'Submetido'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
    ], default='rascunho')
    data_submissao = models.DateTimeField(null=True, blank=True)
    data_aprovacao = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Plano de Trabalho'
        verbose_name_plural = 'Planos de Trabalho'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.titulo} - {self.aluno.nome}'

class Relatorio(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    bolsa = models.ForeignKey(Bolsa, on_delete=models.CASCADE, related_name='relatorios')
    aluno = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='relatorios')
    tipo = models.CharField(max_length=10, choices=[
        ('parcial', 'Parcial'),
        ('final', 'Final'),
    ])
    titulo = models.CharField(max_length=255)
    conteudo = models.TextField(blank=True)
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fim = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=[
        ('rascunho', 'Rascunho'),
        ('submetido', 'Submetido'),
        ('avaliado', 'Avaliado'),
        ('aprovado', 'Aprovado'),
        ('reprovado', 'Reprovado'),
    ], default='rascunho')
    nota = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    observacoes = models.TextField(blank=True)
    data_submissao = models.DateTimeField(null=True, blank=True)
    data_avaliacao = models.DateTimeField(null=True, blank=True)
    avaliado_por = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True, blank=True, related_name='relatorios_avaliados')

    class Meta:
        verbose_name = 'Relatório'
        verbose_name_plural = 'Relatórios'
        ordering = ['-criado_em']

    def __str__(self):
        return f'{self.tipo} - {self.titulo} - {self.aluno.nome}'
