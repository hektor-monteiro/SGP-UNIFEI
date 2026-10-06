"""Aplica a nota automática por financiamento externo aos registros existentes.

Regra da UNIFEI (§3.4): projeto com recursos externos > 0 recebe nota
10,00 e o status 'avaliada' sem passar pela avaliação por pares. A
migração de dados aplica a mesma regra que o ``save()`` do model passa
a aplicar a partir de agora, deixando registros importados/antigos
coerentes com o novo comportamento.
"""
from decimal import Decimal

from django.db import migrations


def aplicar_nota_automatica(apps, schema_editor):
    """Marca como automática a nota de todos os projetos com recursos externos."""
    Projeto = apps.get_model('projetos', 'Projeto')
    Projeto.objects.filter(recursos_externos__gt=0).update(
        nota=Decimal('10.00'),
        status_avaliacao='avaliada',
        nota_automatica=True,
    )


def reverter_nota_automatica(apps, schema_editor):
    """Desliga apenas o flag da nota automática.

    A reversão completa do fluxo (volta para a avaliação por pares)
    acontece no ``save()`` do model quando os recursos externos são
    removidos — aqui não há como saber o estado anterior de cada linha.
    """
    Projeto = apps.get_model('projetos', 'Projeto')
    Projeto.objects.filter(nota_automatica=True).update(nota_automatica=False)


class Migration(migrations.Migration):

    dependencies = [
        ('projetos', '0007_projeto_nota_automatica_alter_projeto_nota'),
    ]

    operations = [
        migrations.RunPython(aplicar_nota_automatica, reverter_nota_automatica),
    ]
