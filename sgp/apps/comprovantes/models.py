from django.db import models
import uuid
import hashlib
from apps.core.models import TimeStampedModel
from apps.projetos.models import Pessoa, Projeto
from apps.bolsas.models import Bolsa
from apps.editais.models import Edital

class Comprovante(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tipo = models.CharField(max_length=20, choices=[
        ('bolsa', 'Bolsa'),
        ('participacao_projeto', 'Participação em Projeto'),
        ('avaliacao', 'Avaliação'),
    ])
    pessoa = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name='comprovantes')
    projeto = models.ForeignKey(Projeto, on_delete=models.CASCADE, null=True, blank=True, related_name='comprovantes')
    bolsa = models.ForeignKey(Bolsa, on_delete=models.CASCADE, null=True, blank=True, related_name='comprovantes')
    edital = models.ForeignKey(Edital, on_delete=models.CASCADE, null=True, blank=True, related_name='comprovantes')
    descricao = models.TextField(blank=True)
    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)
    carga_horaria = models.PositiveIntegerField(null=True, blank=True)
    codigo_verificacao = models.CharField(max_length=32, unique=True)
    emitido_por = models.ForeignKey('auth.User', on_delete=models.SET_NULL, null=True, related_name='comprovantes_emitidos')
    emitido_em = models.DateTimeField(auto_now_add=True)
    arquivo = models.FileField(upload_to='comprovantes/', null=True, blank=True)

    class Meta:
        verbose_name = 'Comprovante'
        verbose_name_plural = 'Comprovantes'
        ordering = ['-emitido_em']

    def save(self, *args, **kwargs):
        if not self.codigo_verificacao:
            hash_input = f'{self.pessoa.id}{self.projeto_id or ""}}{self.bolsa_id or ""}}{self.edital_id or ""}'
            self.codigo_verificacao = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.tipo} - {self.pessoa.nome} - {self.codigo_verificacao}'
