"""Testes do painel de indicadores (§5 — governamentais e de efetividade)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Instituicao, Perfil, Fomentador
from apps.editais.models import Edital
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Pessoa, Projeto, Proposta
from apps.bolsas.models import Bolsa, ModalidadeBolsa


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


class IndicadoresBase(TestCase):
    """Base com dados de todos os grupos de indicadores."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.fomentador, _ = Fomentador.objects.get_or_create(
            sigla='CNPq', defaults={'nome': 'Conselho Nacional de Desenvolvimento Científico',
                                    'tipo': 'bolsa'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Ind', email='inddoc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno Ind 1', email='indalu1@alunos.edu.br', tipo='aluno',
            matricula='20260051', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno Ind 2', email='indalu2@alunos.edu.br', tipo='aluno',
            matricula='20260052', instituicao=inst,
        )
        self.externo = Pessoa.objects.create(
            nome='Colaborador Externo', email='indext@empresa.com.br',
            tipo='docente', instituicao=inst,
        )
        self.projeto_vigente = Projeto.objects.create(
            codigo='PVIND-2026', titulo='Projeto vigente',
            data_registro=date(2026, 1, 1), data_inicio=date(2026, 1, 1),
            coordenador=self.docente, instituicao=inst,
            recursos_internos=Decimal('1000.00'), recursos_externos=Decimal('2000.00'),
        )
        self.projeto_concluido = Projeto.objects.create(
            codigo='PVIND-C-2026', titulo='Projeto concluído',
            data_registro=date(2026, 1, 1), data_inicio=date(2026, 1, 1),
            data_termino=date(2026, 3, 1),  # 59 dias
            status='concluido', instituicao=inst,
        )
        self.bolsa_ativa = Bolsa.objects.create(
            projeto=self.projeto_vigente, aluno=self.aluno1, modalidade=self.modalidade,
            fomentador=self.fomentador,
            data_inicio=date(2026, 5, 1), data_fim=date(2026, 11, 30),
        )
        self.bolsa_encerrada = Bolsa.objects.create(
            projeto=self.projeto_vigente, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2025, 5, 1), data_fim=date(2025, 11, 30),
            status='encerrada',
        )
        MembroEquipe.objects.create(
            projeto=self.projeto_vigente, pessoa=self.externo, funcao='externo',
            data_entrada=date(2026, 1, 1),
        )
        self.edital = Edital.objects.create(
            codigo='EDT-IND-2026', titulo='Edital indicadores 2026',
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 4, 1),
            status='publicado', modalidade=self.modalidade,
        )
        Proposta.objects.create(
            titulo='Proposta aprovada', edital=self.edital, submetido_por=self.aluno1,
            status='aprovada', nota_final=Decimal('8.50'),
        )
        Proposta.objects.create(
            titulo='Proposta reprovada', edital=self.edital, submetido_por=self.aluno2,
            status='reprovada', nota_final=Decimal('4.00'),
        )

        self.u_aluno = _criar_usuario('alu_ind', Perfil.PERFIL_ALUNO, self.aluno1)
        self.u_doc = _criar_usuario('doc_ind', Perfil.PERFIL_DOCENTE, self.docente)
        self.u_tec = _criar_usuario('tec_ind', Perfil.PERFIL_TECNICO)
        self.u_super = User.objects.create_superuser('root_ind', password='x')


class IndicadoresAcessoTests(IndicadoresBase):
    """Permissões do painel de indicadores."""

    def test_exige_login(self):
        resp = self.client.get(reverse('indicadores'))
        self.assertEqual(resp.status_code, 302)

    def test_aluno_e_docente_recebem_403(self):
        for username in ('alu_ind', 'doc_ind'):
            self.client.login(username=username, password='x')
            resp = self.client.get(reverse('indicadores'))
            self.assertEqual(resp.status_code, 403, username)
            self.client.logout()

    def test_tecnico_acede(self):
        self.client.login(username='tec_ind', password='x')
        resp = self.client.get(reverse('indicadores'))
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'relatorios/indicadores.html')
        self.assertContains(resp, 'Indicadores de pesquisa')

    def test_superuser_acede(self):
        self.client.login(username='root_ind', password='x')
        resp = self.client.get(reverse('indicadores'))
        self.assertEqual(resp.status_code, 200)

    def test_painel_tecnico_link_para_indicadores(self):
        self.client.login(username='tec_ind', password='x')
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, reverse('indicadores'))


class Indicadores51Tests(IndicadoresBase):
    """§5.1 — Indicadores governamentais e de agências de fomento."""

    def setUp(self):
        super().setUp()
        self.client.login(username='tec_ind', password='x')
        self.resp = self.client.get(reverse('indicadores'))
        self.ctx = self.resp.context

    def test_bolsas_por_modalidade_e_fomentador(self):
        modalidades = self.ctx['bolsas_modalidade']
        self.assertEqual(len(modalidades), 1)
        self.assertEqual(modalidades[0]['modalidade__sigla'], 'PIBIC')
        self.assertEqual(modalidades[0]['total'], 2)
        self.assertEqual(modalidades[0]['ativas'], 1)
        fomentadores = self.ctx['bolsas_fomentador']
        # uma bolsa sem fomentador aparece como None (template: "Não informado")
        self.assertEqual(
            {f['fomentador__sigla'] for f in fomentadores},
            {'CNPq', None},
        )

    def test_taxa_conclusao_de_projetos(self):
        # 1 concluído de 2 = 50%
        self.assertEqual(self.ctx['total_projetos'], 2)
        self.assertEqual(self.ctx['projetos_concluidos'], 1)
        self.assertEqual(self.ctx['taxa_conclusao'], 50.0)

    def test_alunos_que_concluiram_bolsa(self):
        self.assertEqual(self.ctx['alunos_concluiram'], 1)

    def test_membros_externos(self):
        self.assertEqual(self.ctx['externos_total'], 1)
        self.assertEqual(self.ctx['externos_ativos'], 1)

    def test_execucao_orcamentaria(self):
        self.assertEqual(self.ctx['recursos_internos'], Decimal('1000.00'))
        self.assertEqual(self.ctx['recursos_externos'], Decimal('2000.00'))

    def test_todos_de_indicadores_sem_fonte(self):
        """Campos sem origem no modelo ficam marcados com TODO na tela."""
        self.assertContains(self.resp, 'TODO')
        self.assertContains(self.resp, 'área/departamento')
        self.assertContains(self.resp, 'gênero, raça e região')


class Indicadores52Tests(IndicadoresBase):
    """§5.2 — Indicadores de efetividade."""

    def setUp(self):
        super().setUp()
        self.client.login(username='tec_ind', password='x')
        self.resp = self.client.get(reverse('indicadores'))
        self.ctx = self.resp.context

    def test_evolucao_temporal_de_bolsas_e_projetos(self):
        evolucao_bolsas = self.ctx['evolucao_bolsas']
        self.assertEqual(
            [(e['ano'].year, e['total']) for e in evolucao_bolsas],
            [(2025, 1), (2026, 1)],
        )
        # barras proporcionais ao maior total
        self.assertTrue(all('barra' in e for e in evolucao_bolsas))
        self.assertEqual(len(self.ctx['evolucao_projetos']), 1)
        self.assertEqual(self.ctx['evolucao_projetos'][0]['total'], 2)

    def test_taxa_de_sucesso_em_editais(self):
        self.assertEqual(self.ctx['taxa_sucesso_editais'], 50.0)
        editais = self.ctx['editais_taxas']
        self.assertEqual(len(editais), 1)
        self.assertEqual(editais[0]['codigo'], 'EDT-IND-2026')
        self.assertEqual(editais[0]['total'], 2)
        self.assertEqual(editais[0]['aprovadas'], 1)
        self.assertEqual(editais[0]['taxa'], 50.0)

    def test_tempo_medio_de_conclusao(self):
        # 01/01/2026 → 01/03/2026 = 31 (jan) + 28 (fev) = 59 dias
        self.assertEqual(self.ctx['tempo_medio_dias'], 59)

    def test_orientados_por_docente(self):
        orientandos = self.ctx['orientandos']
        self.assertEqual(len(orientandos), 1)
        self.assertEqual(orientandos[0]['projeto__coordenador__nome'], 'Docente Ind')
        # só a bolsa ativa conta (a encerrada fica de fora)
        self.assertEqual(orientandos[0]['orientandos'], 1)

    def test_retencao_de_bolsistas(self):
        # 0 alunos com mais de uma bolsa de 2 alunos com bolsa
        self.assertEqual(self.ctx['alunos_com_bolsa'], 2)
        self.assertEqual(self.ctx['alunos_renovaram'], 0)
        self.assertEqual(self.ctx['taxa_renovacao'], 0.0)
