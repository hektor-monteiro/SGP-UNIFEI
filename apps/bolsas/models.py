from django.db import models
import uuid
from apps.core.models import TimeStampedModel, Fomentador
from apps.projetos.models import Pessoa, Projeto

class ModalidadeBolsa(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sigla = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Modalidade de Bolsa'
        verbose_name_plural = 'Modalidades de Bolsa'
        ordering = ['sigla']

    def __str__(self):
        return f'{self.sigla} - {self.nome}'

class Bolsa(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='bolsas')
    aluno = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='bolsas')
    modalidade = models.ForeignKey(ModalidadeBolsa, on_delete=models.PROTECT)
    fomentador = models.ForeignKey(Fomentador, on_delete=models.SET_NULL, null=True, blank=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    status = models.CharField(max_length=10, choices=[
        ('ativa', 'Ativa'),
        ('encerrada', 'Encerrada'),
        ('cancelada', 'Cancelada'),
        ('suspensa', 'Suspensa'),
    ], default='ativa')
    valor_mensal = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        verbose_name = 'Bolsa'
        verbose_name_plural = 'Bolsas'
        ordering = ['-data_inicio']
        constraints = [
            models.UniqueConstraint(
                fields=['aluno'],
                condition=models.Q(status='ativa'),
                name='unique_bolsa_ativa_por_aluno'
            )
        ]

    def __str__(self):
        return f'{self.aluno.nome} - {self.modalidade.sigla}'
