"""Plano de Trabalho: descrição vira resumo + anexo de documento em PDF.

- O sistema guarda apenas metadados + `resumo` (texto curto que alimenta
  a busca); objetivos, metodologia e cronograma passam a viver no PDF.
- Migração de dados: o 1º parágrafo da descrição antiga vira `resumo`
  antes de as colunas antigas serem removidas (nada se perde do que era
  texto corrido; a redação completa já não é editável no sistema).
"""
import apps.core.validators
from django.db import migrations, models


def descricao_para_resumo(apps, schema_editor):
    """Copia o 1º parágrafo da descrição antiga para o resumo."""
    PlanoTrabalho = apps.get_model('relatorios', 'PlanoTrabalho')
    for plano in PlanoTrabalho.objects.exclude(descricao='').iterator():
        texto = (plano.descricao or '').strip()
        if not texto:
            continue
        paragrafo = texto.split('\n\n')[0].replace('\n', ' ').strip()
        plano.resumo = paragrafo[:1000]
        plano.save(update_fields=['resumo'])


def resumo_para_descricao(apps, schema_editor):
    """Reversão: devolve o resumo para a descrição (rollback possível)."""
    PlanoTrabalho = apps.get_model('relatorios', 'PlanoTrabalho')
    for plano in PlanoTrabalho.objects.exclude(resumo='').iterator():
        plano.descricao = plano.resumo
        plano.save(update_fields=['descricao'])


class Migration(migrations.Migration):

    dependencies = [
        ('relatorios', '0002_plano_trabalho_projeto'),
    ]

    operations = [
        migrations.AddField(
            model_name='planotrabalho',
            name='resumo',
            field=models.TextField(
                blank=True,
                help_text='Texto curto (até 1000 caracteres) exibido na tela e usado na busca do sistema.',
                max_length=1000,
                verbose_name='Resumo',
            ),
        ),
        migrations.RunPython(descricao_para_resumo, resumo_para_descricao),
        migrations.AddField(
            model_name='planotrabalho',
            name='arquivo_pdf',
            field=models.FileField(
                blank=True,
                help_text='Plano de trabalho completo em PDF (até 15 MB). Obrigatório para submeter (status diferente de Rascunho).',
                upload_to='uploads/planos/%Y/%m/',
                validators=[apps.core.validators.validar_pdf],
                verbose_name='Documento (PDF)',
            ),
        ),
        migrations.RemoveField(
            model_name='planotrabalho',
            name='descricao',
        ),
        migrations.RemoveField(
            model_name='planotrabalho',
            name='objetivos',
        ),
        migrations.RemoveField(
            model_name='planotrabalho',
            name='metodologia',
        ),
        migrations.RemoveField(
            model_name='planotrabalho',
            name='cronograma',
        ),
    ]
