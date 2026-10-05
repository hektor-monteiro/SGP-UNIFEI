"""Testes do módulo LGPD (§6): consentimento, direito de acesso e auditoria."""
import json
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.core.models import Instituicao, LogAuditoria, Perfil
from apps.editais.models import Avaliacao
from apps.projetos.models import Pessoa, Projeto, Proposta
from apps.relatorios.models import Relatorio


class LgpdTests(TestCase):
    """Testes da página LGPD, exportação de dados e logs de auditoria."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente LGPD', email='lgpddoc@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno LGPD', email='lgpdalu@alunos.edu.br',
            tipo='aluno', matricula='20260101', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno Outro LGPD', email='lgpdalu2@alunos.edu.br',
            tipo='aluno', matricula='20260102', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PV-LGPD-2026', titulo='Projeto LGPD',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.rel_meu = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno1, tipo='parcial',
            titulo='Relatorio sigiloso do aluno 1',
        )
        bolsa_alheia = Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.rel_alheio = Relatorio.objects.create(
            bolsa=bolsa_alheia, aluno=self.aluno2, tipo='parcial',
            titulo='Relatorio sigiloso do aluno 2',
        )
        self.proposta = Proposta.objects.create(
            titulo='Proposta sigilosa', submetido_por=self.aluno1,
        )

        self.user_alu = User.objects.create_user('alu_lgp', password='x')
        Perfil.objects.create(user=self.user_alu, perfil=Perfil.PERFIL_ALUNO, pessoa=self.aluno1)
        self.user_alu2 = User.objects.create_user('alu2_lgp', password='x')
        Perfil.objects.create(user=self.user_alu2, perfil=Perfil.PERFIL_ALUNO, pessoa=self.aluno2)
        self.user_tec = User.objects.create_user('tec_lgp', password='x')
        Perfil.objects.create(user=self.user_tec, perfil=Perfil.PERFIL_TECNICO)
        self.user_doc = User.objects.create_user('doc_lgp', password='x')
        Perfil.objects.create(
            user=self.user_doc, perfil=Perfil.PERFIL_DOCENTE, pessoa=self.docente,
        )
        self.user_admin = User.objects.create_superuser('adm_lgp', password='x')

        self.avaliacao = Avaliacao.objects.create(
            tipo='proposta', proposta=self.proposta, avaliador=self.user_tec,
        )

    # ------------------------------------------------------------------
    # Página LGPD e consentimento
    # ------------------------------------------------------------------

    def test_lgpd_exige_login(self):
        self.assertEqual(self.client.get(reverse('lgpd')).status_code, 302)

    def test_lgpd_pagina_mostra_direitos_e_dpo(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.get(reverse('lgpd'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Consentimento')
        self.assertContains(resp, 'dpo@unifei.edu.br')
        self.assertContains(resp, 'RIPD')
        # Aluno não vê o link dos logs de auditoria
        self.assertNotContains(resp, reverse('auditoria'))

    def test_tecnico_ve_link_de_auditoria_na_lgpd(self):
        self.client.login(username='tec_lgp', password='x')
        resp = self.client.get(reverse('lgpd'))
        self.assertContains(resp, reverse('auditoria'))

    def test_consentimento_registra_data(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.post(reverse('lgpd_consentimento'), follow=True)
        self.assertEqual(resp.status_code, 200)
        perfil = Perfil.objects.get(user=self.user_alu)
        self.assertTrue(perfil.consentimento_lgpd)
        self.assertIsNotNone(perfil.data_consentimento)
        self.assertContains(resp, 'Consentimento registrado')

    def test_consentimento_anonimo_nao_registra(self):
        resp = self.client.post(reverse('lgpd_consentimento'))
        self.assertEqual(resp.status_code, 302)
        perfil = Perfil.objects.get(user=self.user_alu)
        self.assertFalse(perfil.consentimento_lgpd)

    def test_superuser_sem_perfil_nao_quebra(self):
        self.client.login(username='adm_lgp', password='x')
        resp = self.client.get(reverse('lgpd'))
        self.assertEqual(resp.status_code, 200)
        # Superusuário não tem Perfil — formulário de consentimento ausente
        self.assertNotContains(resp, 'Registrar consentimento')
        resp = self.client.post(reverse('lgpd_consentimento'))
        self.assertEqual(resp.status_code, 302)

    # ------------------------------------------------------------------
    # Direito de acesso — exportação dos próprios dados (JSON)
    # ------------------------------------------------------------------

    def test_meus_dados_exige_login(self):
        self.assertEqual(
            self.client.get(reverse('lgpd_meus_dados')).status_code, 302,
        )

    def test_meus_dados_exporta_proprios_dados(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.get(reverse('lgpd_meus_dados'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('json', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])
        dados = json.loads(resp.content)
        self.assertEqual(dados['usuario']['username'], 'alu_lgp')
        self.assertEqual(dados['pessoa']['nome'], 'Aluno LGPD')
        self.assertEqual(len(dados['bolsas']), 1)
        self.assertEqual(dados['bolsas'][0]['modalidade__sigla'], 'PIBIC')
        titulos = [r['titulo'] for r in dados['relatorios']]
        self.assertIn('Relatorio sigiloso do aluno 1', titulos)

    def test_meus_dados_nao_vaza_dados_alheios(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.get(reverse('lgpd_meus_dados'))
        conteudo = resp.content.decode()
        self.assertNotIn('Relatorio sigiloso do aluno 2', conteudo)
        dados = json.loads(resp.content)
        self.assertEqual(len(dados['relatorios']), 1)

    def test_meus_dados_inclui_avaliacoes_do_avaliador(self):
        self.client.login(username='tec_lgp', password='x')
        resp = self.client.get(reverse('lgpd_meus_dados'))
        dados = json.loads(resp.content)
        self.assertEqual(len(dados['avaliacoes_de_propostas']), 1)
        self.assertEqual(
            dados['avaliacoes_de_propostas'][0]['proposta__titulo'],
            'Proposta sigilosa',
        )

    def test_painel_oferece_link_lgpd(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, reverse('lgpd'))

    # ------------------------------------------------------------------
    # Logs de auditoria (§6)
    # ------------------------------------------------------------------

    def test_auditoria_exige_login(self):
        self.assertEqual(self.client.get(reverse('auditoria')).status_code, 302)

    def test_auditoria_aluno_negado_e_logado(self):
        self.client.login(username='alu_lgp', password='x')
        resp = self.client.get(reverse('auditoria'))
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='acesso_negado',
                usuario=self.user_alu,
                caminho=reverse('auditoria'),
            ).exists(),
        )

    def test_auditoria_tecnico_lista_registros(self):
        self.client.login(username='tec_lgp', password='x')
        resp = self.client.get(reverse('auditoria'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Logs de auditoria')

    def test_auditoria_filtro_por_acao(self):
        self.client.login(username='tec_lgp', password='x')
        resp = self.client.get(reverse('auditoria'), {'acao': 'login'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['filtros']['acao'], 'login')

    def test_login_registrado_no_log(self):
        self.client.login(username='alu_lgp', password='x')
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='login', usuario=self.user_alu,
            ).exists(),
        )

    def test_logout_registrado_no_log(self):
        self.client.login(username='alu_lgp', password='x')
        self.client.post(reverse('logout'))
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='logout', usuario=self.user_alu,
            ).exists(),
        )

    def test_escrita_registrada_no_log(self):
        self.client.login(username='alu_lgp', password='x')
        self.client.post(reverse('lgpd_consentimento'))
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='escrita',
                usuario=self.user_alu,
                caminho=reverse('lgpd_consentimento'),
                metodo='POST',
            ).exists(),
        )

    def test_exclusao_registrada_no_log(self):
        self.client.login(username='alu_lgp', password='x')
        self.client.delete(reverse('lgpd'))
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='exclusao',
                usuario=self.user_alu,
                metodo='DELETE',
            ).exists(),
        )

    def test_leitura_comum_nao_gera_log(self):
        self.client.login(username='alu_lgp', password='x')
        antes = LogAuditoria.objects.count()
        self.client.get(reverse('dashboard'))
        # Leituras (GET) comuns não são auditadas
        self.assertEqual(LogAuditoria.objects.count(), antes)

    def test_link_auditoria_conforme_perfil(self):
        """Sem Perfil: sem link de auditoria (rota 403); superusuário: vê."""
        User.objects.create_user('sem_perfil_lgp', password='x')
        self.client.login(username='sem_perfil_lgp', password='x')
        resp = self.client.get(reverse('lgpd'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse('auditoria'))
        self.assertEqual(self.client.get(reverse('auditoria')).status_code, 403)

        self.client.logout()
        self.client.login(username='adm_lgp', password='x')
        resp = self.client.get(reverse('lgpd'))
        self.assertContains(resp, reverse('auditoria'))
