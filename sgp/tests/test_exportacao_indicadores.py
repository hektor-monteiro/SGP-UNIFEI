"""Testes da exportação CSV dos indicadores (§5)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.core.models import Fomentador, Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


class ExportacaoIndicadoresTests(TestCase):
    """Testes da rota /indicadores/csv/ (permissões e conteúdo)."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.fomentador, _ = Fomentador.objects.get_or_create(
            sigla='FAPEMIG', defaults={'nome': 'FAPEMIG', 'tipo': 'estadual'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente CSV', email='csvdoc@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno CSV', email='csvalu@alunos.edu.br',
            tipo='aluno', matricula='20260301', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PV-CSV-2026', titulo='Projeto para exportação',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
            recursos_internos=Decimal('1000.50'),
            recursos_externos=Decimal('2000.25'),
        )
        Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno, modalidade=self.modalidade,
            fomentador=self.fomentador,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )

        _criar_usuario('tec_csv', Perfil.PERFIL_TECNICO)
        _criar_usuario('dir_csv', Perfil.PERFIL_DIRETOR)
        _criar_usuario('alu_csv', Perfil.PERFIL_ALUNO, self.aluno)

    def _csv(self):
        resp = self.client.get(reverse('indicadores_csv'))
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_csv_exige_login(self):
        self.assertEqual(
            self.client.get(reverse('indicadores_csv')).status_code, 302,
        )

    def test_csv_aluno_negado(self):
        self.client.login(username='alu_csv', password='x')
        self.assertEqual(
            self.client.get(reverse('indicadores_csv')).status_code, 403,
        )

    def test_csv_headers_de_download(self):
        self.client.login(username='tec_csv', password='x')
        resp = self._csv()
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.csv', resp['Content-Disposition'])
        # BOM UTF-8 para o Excel abrir com acentos
        self.assertTrue(resp.content.startswith(b'\xef\xbb\xbf'))

    def test_csv_contem_secoes_do_painel(self):
        self.client.login(username='tec_csv', password='x')
        texto = self._csv().content.decode('utf-8-sig')
        for trecho in (
            'SGP-UNIFEI — Indicadores de pesquisa',
            'Emitido por;tec_csv',
            '5.1 Governamentais e de agências de fomento',
            '5.2 Indicadores de efetividade',
            'Bolsas por modalidade',
            'Sucesso por edital',
            'Orientados por docente',
        ):
            self.assertIn(trecho, texto)

    def test_csv_contem_dados_conhecidos(self):
        self.client.login(username='tec_csv', password='x')
        texto = self._csv().content.decode('utf-8-sig')
        linhas = texto.splitlines()
        # Modalidade e fomentador do seed de teste
        self.assertIn('PIBIC;1;1', linhas)
        self.assertIn('FAPEMIG;1', linhas)
        # Números com vírgula decimal (convenção pt-BR)
        self.assertIn('Recursos internos vinculados (R$);1000,50', texto)
        self.assertIn('Recursos externos vinculados (R$);2000,25', texto)
        # Contagem de projetos da visão geral
        self.assertIn(f'Projetos;{Projeto.objects.count()}', linhas)

    def test_csv_diretor_acessa(self):
        self.client.login(username='dir_csv', password='x')
        self.assertEqual(self._csv().status_code, 200)

    def test_painel_oferece_botao_de_download(self):
        self.client.login(username='tec_csv', password='x')
        resp = self.client.get(reverse('indicadores'))
        self.assertContains(resp, reverse('indicadores_csv'))
