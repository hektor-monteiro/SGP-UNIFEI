"""Relatório: conteúdo vira resumo + anexo de documento em PDF.

- O sistema guarda metadados + `resumo` (texto curto que alimenta a
  busca); a redação completa do relatório passa a viver no PDF anexado.
- Migração de dados: o 1º parágrafo do conteúdo antigo vira `resumo`
  antes de a coluna ser removida.
"""
import apps.core.validators
from django.db import migrations, models


def conteudo_para_resumo(apps, schema_editor):
    """Copia o 1º parágrafo do conteúdo antigo para o resumo."""
    Relatorio = apps.get_model('relatorios', 'Relatorio')
    for relatorio in Relatorio.objects.exclude(conteudo='').iterator():
        texto = (relatorio.conteudo or '').strip()
        if not texto:
            continue
        paragrafo = texto.split('\n\n')[0].replace('\n', ' ').strip()
        relatorio.resumo = paragrafo[:1000]
        relatorio.save(update_fields=['resumo'])


def resumo_para_conteudo(apps, schema_editor):
    """Reversão: devolve o resumo para o conteúdo (rollback possível)."""
    Relatorio = apps.get_model('relatorios', 'Relatorio')
    for relatorio in Relatorio.objects.exclude(resumo='').iterator():
        relatorio.conteudo = relatorio.resumo
        relatorio.save(update_fields=['conteudo'])


class Migration(migrations.Migration):

    dependencies = [
        ('relatorios', '0003_plano_resumo_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='relatorio',
            name='resumo',
            field=models.TextField(
                blank=True,
                help_text='Texto curto (até 1000 caracteres) exibido na tela e usado na busca do sistema.',
                max_length=1000,
                verbose_name='Resumo',
            ),
        ),
        migrations.RunPython(conteudo_para_resumo, resumo_para_conteudo),
        migrations.AddField(
            model_name='relatorio',
            name='arquivo_pdf',
            field=models.FileField(
                blank=True,
                help_text='Relatório completo em PDF (até 15 MB). Obrigatório para submeter para avaliação.',
                upload_to='uploads/relatorios/%Y/%m/',
                validators=[apps.core.validators.validar_pdf],
                verbose_name='Documento (PDF)',
            ),
        ),
        migrations.RemoveField(
            model_name='relatorio',
            name='conteudo',
        ),
    ]
