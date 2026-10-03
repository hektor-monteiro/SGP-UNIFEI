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
