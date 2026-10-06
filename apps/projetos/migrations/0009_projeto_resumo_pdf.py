"""Projeto: descrição vira resumo + anexo de documento em PDF.

- `resumo` substitui `descricao`: texto curto (até 1000 caracteres) que
  alimenta a busca do sistema; a redação completa passa a viver no PDF.
- Migração de dados: o 1º parágrafo da descrição antiga vira `resumo`
  antes de a coluna antiga ser removida (nenhum texto se perde).
"""
import apps.core.validators
from django.db import migrations, models


def descricao_para_resumo(apps, schema_editor):
    """Copia o 1º parágrafo da descrição antiga para o resumo."""
    Projeto = apps.get_model('projetos', 'Projeto')
    for projeto in Projeto.objects.exclude(descricao='').iterator():
        texto = (projeto.descricao or '').strip()
        if not texto:
            continue
        paragrafo = texto.split('\n\n')[0].replace('\n', ' ').strip()
        projeto.resumo = paragrafo[:1000]
        projeto.save(update_fields=['resumo'])


def resumo_para_descricao(apps, schema_editor):
    """Reversão: devolve o resumo para a descrição (rollback possível)."""
    Projeto = apps.get_model('projetos', 'Projeto')
    for projeto in Projeto.objects.exclude(resumo='').iterator():
        projeto.descricao = projeto.resumo
        projeto.save(update_fields=['descricao'])


class Migration(migrations.Migration):

    dependencies = [
        ('projetos', '0008_nota_automatica_financiamento_externo'),
    ]

    operations = [
        migrations.AddField(
            model_name='projeto',
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
            model_name='projeto',
            name='arquivo_pdf',
            field=models.FileField(
                blank=True,
                help_text='Projeto completo em PDF (até 15 MB). Obrigatório para enviar à avaliação por pares.',
                upload_to='uploads/projetos/%Y/%m/',
                validators=[apps.core.validators.validar_pdf],
                verbose_name='Documento (PDF)',
            ),
        ),
        migrations.RemoveField(
            model_name='projeto',
            name='descricao',
        ),
    ]
