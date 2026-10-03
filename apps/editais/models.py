from django.db import models
import uuid
from apps.core.models import TimeStampedModel
from apps.bolsas.models import ModalidadeBolsa
from apps.projetos.models import Proposta

class Edital(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codigo = models.CharField(max_length=50, unique=True)
    titulo = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=15, choices=[
        ('rascunho', 'Rascunho'),
        ('publicado', 'Publicado'),
        ('em_andamento', 'Em Andamento'),
        ('encerrado', 'Encerrado'),
        ('cancelado', 'Cancelado'),
    ], default='rascunho')
    modalidade = models.ForeignKey(ModalidadeBolsa, on_delete=models.SET_NULL, null=True, blank=True)
    criado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='editais_criados')
    validado_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='editais_validados')
    data_validacao = models.DateTimeField(null=True, blank=True)

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
    ])
    proposta = models.ForeignKey(Proposta, on_delete=models.CASCADE, null=True, blank=True, related_name='avaliacoes')
    avaliador = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='avaliacoes')
    nota = models.DecimalField(max_digits=4, decimal_places=2)
    parecer = models.TextField(blank=True)
    data_avaliacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Avaliação'
        verbose_name_plural = 'Avaliações'
        ordering = ['-data_avaliacao']

    def __str__(self):
        return f'{self.tipo} - {self.nota}'
