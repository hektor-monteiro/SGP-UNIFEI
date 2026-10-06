"""Teste do seed demo: variedade de dados para os indicadores (§5)."""
import random
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase

from apps.bolsas.models import Bolsa
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Projeto


class PopulateDemoIndicadoresTests(TestCase):
    """populate_demo deve gerar dados variados para o painel de indicadores."""

    def test_seed_gera_variedade_para_indicadores(self):
        random.seed(42)
        call_command('populate_demo', stdout=StringIO())

        # §5.1 — conclusão, recursos, membros externos e bolsas concluídas
        self.assertTrue(Projeto.objects.filter(status='concluido').exists())
        self.assertTrue(
            Projeto.objects.filter(recursos_internos__isnull=False).exists(),
        )
        self.assertTrue(MembroEquipe.objects.filter(funcao='externo').exists())
        self.assertTrue(Bolsa.objects.filter(status='encerrada').exists())

        # §5.2 — renovação: aluno com mais de uma bolsa
        self.assertTrue(
            Bolsa.objects.values('aluno')
            .annotate(n=Count('id'))
            .filter(n__gte=2)
            .exists(),
        )

        # Aluno demo (aluno1 = alunos[0] = Ana) tem bolsa: o painel
        # inicial do demo não pode nascer vazio em instalação nova
        from apps.projetos.models import Pessoa
        ana = Pessoa.objects.get(nome='Ana Beatriz Silva')
        self.assertTrue(Bolsa.objects.filter(aluno=ana).exists())
        self.assertTrue(
            Bolsa.objects.filter(aluno=ana, status='ativa').exists(),
        )

        # Coerência de datas: concluídos terminaram no passado e
        # início ≤ término em todos os projetos
        hoje = date.today()
        for projeto in Projeto.objects.all():
            if projeto.status == 'concluido':
                self.assertIsNotNone(projeto.data_termino)
                self.assertLess(projeto.data_termino, hoje, projeto.codigo)
            if projeto.data_termino:
                self.assertLessEqual(
                    projeto.data_inicio, projeto.data_termino, projeto.codigo,
                )

        # Recursos são valores positivos quando preenchidos
        for projeto in Projeto.objects.exclude(recursos_internos=None):
            self.assertGreater(projeto.recursos_internos, Decimal('0'))

    def test_seed_coerente_com_nota_automatica(self):
        """§3.4: financiamento externo → nota 10,00 automática.

        E a avaliação por pares simulada pelo seed só acontece em
        projetos sem recursos externos (com eles a nota é automática).
        """
        random.seed(42)
        call_command('populate_demo', stdout=StringIO())

        externos = Projeto.objects.filter(recursos_externos__gt=0)
        self.assertTrue(externos.exists())
        self.assertEqual(
            externos.exclude(
                status_avaliacao='avaliada',
                nota=Decimal('10.00'),
                nota_automatica=True,
            ).count(),
            0,
        )

        # O seed cobre os dois lados do indicador
        self.assertTrue(
            Projeto.objects.filter(recursos_externos__isnull=True).exists(),
        )

        # Avaliação por pares simulada só em projetos sem financiamento
        avaliados = Projeto.objects.filter(
            avaliacoes__tipo='projeto',
        ).distinct()
        self.assertTrue(avaliados.exists())
        self.assertEqual(
            avaliados.filter(recursos_externos__gt=0).count(), 0,
        )

        # Fluxo continua coberto: projeto submetido aguardando alocação
        self.assertTrue(
            Projeto.objects.filter(status_avaliacao='submetido').exists(),
        )
