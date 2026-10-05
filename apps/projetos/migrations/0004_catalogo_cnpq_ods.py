"""Carrega o catálogo ODS + Áreas do Conhecimento do CNPq.

Fonte: apps/projetos/data/catalogo_cnpq_ods.json — Tabela de Áreas do
Conhecimento do CNPq (Lattes, gerada em 30/06/2025) e os 17 ODS da ONU
em pt-BR. Carga idempotente (get_or_create pela chave única).
"""
import json
from pathlib import Path

from django.db import migrations


def carregar_catalogo(apps, schema_editor):
    """Insere as referências de ODS e da hierarquia CNPq."""
    caminho = (
        Path(__file__).resolve().parent.parent / 'data' / 'catalogo_cnpq_ods.json'
    )
    dados = json.loads(caminho.read_text(encoding='utf-8'))

    ODS = apps.get_model('projetos', 'ODS')
    GrandeArea = apps.get_model('projetos', 'GrandeAreaConhecimento')
    Area = apps.get_model('projetos', 'AreaConhecimento')
    Subarea = apps.get_model('projetos', 'SubareaConhecimento')

    for item in dados['ods']:
        ODS.objects.get_or_create(numero=item['numero'], defaults={'nome': item['nome']})

    pk_grandes = {}
    for item in dados['grande_areas']:
        obj, _ = GrandeArea.objects.get_or_create(
            codigo=item['codigo'], defaults={'nome': item['nome']},
        )
        pk_grandes[item['codigo']] = obj.pk

    pk_areas = {}
    for item in dados['areas']:
        obj, _ = Area.objects.get_or_create(
            codigo=item['codigo'],
            defaults={
                'nome': item['nome'],
                'grande_area_id': pk_grandes[item['grande_area']],
            },
        )
        pk_areas[item['codigo']] = obj.pk

    for item in dados['subareas']:
        Subarea.objects.get_or_create(
            codigo=item['codigo'],
            defaults={
                'nome': item['nome'],
                'area_id': pk_areas[item['area']],
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ('projetos', '0003_areaconhecimento_grandeareaconhecimento_ods_and_more'),
    ]

    operations = [
        migrations.RunPython(carregar_catalogo, migrations.RunPython.noop),
    ]
