"""Adiciona PlanoTrabalho.projeto (vínculo explícito com o projeto do docente).

Backfill: o projeto é derivado da bolsa vinculada ao plano.
"""
import django.db.models.deletion
from django.db import migrations, models


def preencher_projeto(apps, schema_editor):
    """Preenche projeto a partir de bolsa.projeto nos planos existentes."""
    PlanoTrabalho = apps.get_model('relatorios', 'PlanoTrabalho')
    for plano in PlanoTrabalho.objects.select_related('bolsa').iterator():
        plano.projeto_id = plano.bolsa.projeto_id
        plano.save(update_fields=['projeto_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('relatorios', '0001_initial'),
        ('projetos', '0001_initial'),
        ('bolsas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='planotrabalho',
            name='projeto',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='planos_trabalho',
                to='projetos.projeto',
            ),
        ),
        migrations.RunPython(preencher_projeto, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='planotrabalho',
            name='projeto',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='planos_trabalho',
                to='projetos.projeto',
            ),
        ),
    ]
