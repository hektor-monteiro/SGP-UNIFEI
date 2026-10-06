"""Renomeia o status 'publicado' para 'aprovado' nos editais existentes.

Terminologia nova (requisito §3.1): o que era "Publicado" passa a se
chamar "Aprovado" — aprovação da Diretoria/Reitoria. A submissão de
propostas passa a exigir apenas o status 'em_andamento'.
"""
from django.db import migrations


def renomear_status(apps, schema_editor):
    """Atualiza as linhas antigas para o novo valor do status."""
    Edital = apps.get_model('editais', 'Edital')
    Edital.objects.filter(status='publicado').update(status='aprovado')


def reverter_status(apps, schema_editor):
    """Reversão: volta ao valor antigo 'publicado'."""
    Edital = apps.get_model('editais', 'Edital')
    Edital.objects.filter(status='aprovado').update(status='publicado')


class Migration(migrations.Migration):
    dependencies = [
        ('editais', '0003_alter_edital_status'),
    ]

    operations = [
        migrations.RunPython(renomear_status, reverter_status),
    ]
