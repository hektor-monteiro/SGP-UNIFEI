from django.db import models
import uuid
from apps.core.models import TimeStampedModel
from apps.projetos.models import Pessoa, Projeto

class MembroEquipe(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, related_name='membros')
    pessoa = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='equipes')
    funcao = models.CharField(max_length=15, choices=[
        ('coordenador', 'Coordenador'),
        ('orientador', 'Orientador'),
        ('coorientador', 'Coorientador'),
        ('docente', 'Docente'),
        ('discente', 'Discente'),
        ('tecnico', 'Técnico'),
        ('externo', 'Externo'),
    ])
    carga_horaria = models.PositiveIntegerField(null=True, blank=True, help_text='Carga horária semanal em horas')
    data_entrada = models.DateField()
    data_saida = models.DateField(null=True, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Membro de Equipe'
        verbose_name_plural = 'Membros de Equipe'
        ordering = ['-data_entrada']
        unique_together = ['projeto', 'pessoa', 'funcao']

    def __str__(self):
        return f'{self.pessoa.nome} - {self.funcao} - {self.projeto.codigo}'
