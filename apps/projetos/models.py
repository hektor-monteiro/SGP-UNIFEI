from django.db import models
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
    fomentador = models.ForeignKey(Fomentador, on_delete=models.SET_NULL, null=True, blank=True, related_name='projetos')
    recursos_internos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    recursos_externos = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    coordenador = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True, blank=True, related_name='projetos_coordenados')
    processo_sipac = models.ForeignKey(ProcessoSipac, on_delete=models.SET_NULL, null=True, blank=True)
    instituicao = models.ForeignKey(Instituicao, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'
        ordering = ['-data_registro']

    def __str__(self):
        return f'{self.codigo} - {self.titulo[:50]}'

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
