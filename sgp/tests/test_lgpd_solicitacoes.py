"""Testes das solicitações LGPD (§6): correção, exclusão e anonimização."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.core.models import Instituicao, LogAuditoria, Perfil, SolicitacaoLGPD
from apps.projetos.models import Pessoa, Projeto


class SolicitacaoLgpdTests(TestCase):
    """Fluxo de solicitação de titular: abrir, listar, tratar e anonimizar."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )

        self.docente = Pessoa.objects.create(
            nome='Docente Sol', email='docsol@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        # Aluno com bolsa ativa → bloqueia anonimização
        self.aluno_bloq = Pessoa.objects.create(
            nome='Aluno Com Vínculo', email='alunobloq@alunos.edu.br',
            tipo='aluno', matricula='20261001', instituicao=inst,
        )
        # Aluno sem nenhum vínculo → pode ser anonimizado
        self.aluno_livre = Pessoa.objects.create(
            nome='Aluno Sem Vínculo', email='alunolivre@alunos.edu.br',
            tipo='aluno', matricula='20261002', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PV-SOL-2026', titulo='Projeto Solicitações',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst, status='vigente',
        )
        Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno_bloq,
            modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )

        self.user_bloq = User.objects.create_user('alu_bloq', password='x')
        Perfil.objects.create(
            user=self.user_bloq, perfil=Perfil.PERFIL_ALUNO,
            pessoa=self.aluno_bloq,
        )
        self.user_livre = User.objects.create_user('alu_livre', password='x')
        Perfil.objects.create(
            user=self.user_livre, perfil=Perfil.PERFIL_ALUNO,
            pessoa=self.aluno_livre,
        )
        self.user_tec = User.objects.create_user('tec_sol', password='x')
        Perfil.objects.create(user=self.user_tec, perfil=Perfil.PERFIL_TECNICO)
        self.user_admin = User.objects.create_superuser('adm_sol', password='x')

    def _abrir(self, username, tipo='correcao', descricao='Dado incorreto: X'):
        """Abre uma solicitação via POST e retorna a resposta."""
        self.client.login(username=username, password='x')
        return self.client.post(
            reverse('lgpd_solicitacao_nova'),
            {'tipo': tipo, 'descricao': descricao},
        )

    # ------------------------------------------------------------------
    # Abertura e listagem pelo titular
    # ------------------------------------------------------------------

    def test_lista_exige_login(self):
        self.assertEqual(
            self.client.get(reverse('lgpd_solicitacoes')).status_code, 302,
        )

    def test_aluno_cria_solicitacao_de_correcao(self):
        resp = self._abrir('alu_livre')
        self.assertEqual(resp.status_code, 302)
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.assertEqual(sol.tipo, 'correcao')
        self.assertEqual(sol.status, SolicitacaoLGPD.STATUS_ABERTA)
        self.assertRedirects(
            resp, reverse('lgpd_solicitacao_detalhe', args=[sol.pk]),
        )

    def test_aluno_lista_ve_apenas_as_proprias(self):
        self._abrir('alu_bloq', descricao='Solicitação do aluno com vínculo')
        self._abrir('alu_livre', descricao='Solicitação do aluno livre')
        self.client.login(username='alu_bloq', password='x')
        resp = self.client.get(reverse('lgpd_solicitacoes'))
        self.assertEqual(len(resp.context['solicitacoes']), 1)
        self.assertContains(resp, 'Solicitação do aluno com vínculo')
        self.assertNotContains(resp, 'Solicitação do aluno livre')

    def test_detalhe_de_solicitacao_alheia_retorna_404(self):
        self._abrir('alu_bloq')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_bloq)
        self.client.login(username='alu_livre', password='x')
        resp = self.client.get(
            reverse('lgpd_solicitacao_detalhe', args=[sol.pk]),
        )
        self.assertEqual(resp.status_code, 404)

    def test_solicitacao_duplicada_em_aberto_e_rejeitada(self):
        self._abrir('alu_livre')
        resp = self._abrir('alu_livre')
        self.assertEqual(resp.status_code, 200)  # volta ao form com erro
        self.assertContains(resp, 'já possui uma solicitação')
        self.assertEqual(
            SolicitacaoLGPD.objects.filter(
                titular=self.user_livre, tipo='correcao',
            ).count(),
            1,
        )

    def test_superusuario_nao_abre_solicitacao(self):
        self.client.login(username='adm_sol', password='x')
        resp = self.client.post(
            reverse('lgpd_solicitacao_nova'),
            {'tipo': 'correcao', 'descricao': 'não se aplica'},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(SolicitacaoLGPD.objects.count(), 0)

    # ------------------------------------------------------------------
    # Tratamento pelo encarregado (técnicos+)
    # ------------------------------------------------------------------

    def test_aluno_nao_pode_tratar(self):
        self._abrir('alu_livre')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.client.login(username='alu_livre', password='x')
        resp = self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'concluida', 'justificativa': 'autosserviço'},
        )
        self.assertEqual(resp.status_code, 403)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'aberta')

    def test_tratar_exige_post(self):
        self._abrir('alu_livre')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        resp = self.client.get(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
        )
        self.assertEqual(resp.status_code, 302)

    def test_tecnico_lista_todas_e_filtra(self):
        self._abrir('alu_bloq')
        self._abrir('alu_livre')
        self.client.login(username='tec_sol', password='x')
        resp = self.client.get(reverse('lgpd_solicitacoes'))
        self.assertEqual(len(resp.context['solicitacoes']), 2)
        resp = self.client.get(
            reverse('lgpd_solicitacoes'), {'status': 'aberta'},
        )
        self.assertEqual(len(resp.context['solicitacoes']), 2)
        resp = self.client.get(
            reverse('lgpd_solicitacoes'), {'status': 'concluida'},
        )
        self.assertEqual(len(resp.context['solicitacoes']), 0)

    def test_tecnico_move_para_em_analise(self):
        self._abrir('alu_livre')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.client.login(username='tec_sol', password='x')
        resp = self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'em_analise', 'justificativa': 'em verificação'},
        )
        self.assertEqual(resp.status_code, 302)
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'em_analise')
        self.assertEqual(sol.tratado_por, self.user_tec)
        self.assertIsNotNone(sol.tratado_em)

    def test_concluir_ou_indeferir_exige_justificativa(self):
        self._abrir('alu_livre')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.client.login(username='tec_sol', password='x')
        self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'concluida', 'justificativa': ''},
        )
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'aberta')  # form inválido → não muda

    def test_solicitacao_finalizada_nao_e_retratada(self):
        self._abrir('alu_livre')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.client.login(username='tec_sol', password='x')
        self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'indeferida', 'justificativa': 'sem previsão'},
        )
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'indeferida')
        # Tenta reabrir em seguida — não deve voltar a 'em_analise'
        self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'em_analise', 'justificativa': ''},
        )
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'indeferida')

    # ------------------------------------------------------------------
    # Exclusão com anonimização
    # ------------------------------------------------------------------

    def test_concluir_exclusao_com_vinculos_e_bloqueada(self):
        self._abrir(
            'alu_bloq', tipo='exclusao',
            descricao='Quero sair do sistema',
        )
        sol = SolicitacaoLGPD.objects.get(titular=self.user_bloq)
        self.client.login(username='tec_sol', password='x')
        resp = self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'concluida', 'justificativa': 'ok'},
            follow=True,
        )
        self.assertContains(resp, 'bolsa ativa')
        sol.refresh_from_db()
        self.assertEqual(sol.status, 'aberta')  # não concluiu
        self.aluno_bloq.refresh_from_db()
        self.assertEqual(self.aluno_bloq.nome, 'Aluno Com Vínculo')

    def test_concluir_exclusao_sem_vinculos_anonimiza(self):
        self._abrir(
            'alu_livre', tipo='exclusao',
            descricao='Dados pessoais não são mais necessários',
        )
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)

        self.client.login(username='tec_sol', password='x')
        resp = self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'concluida', 'justificativa': 'sem vínculos'},
        )
        self.assertEqual(resp.status_code, 302)

        sol.refresh_from_db()
        self.assertEqual(sol.status, 'concluida')
        self.assertEqual(sol.tratado_por, self.user_tec)

        # Pessoa anonimizada, mas registro preservado (prestação de contas)
        self.aluno_livre.refresh_from_db()
        self.assertIn('anonimizado', self.aluno_livre.nome)
        self.assertIn('anonimizado.invalid', self.aluno_livre.email)
        self.assertEqual(self.aluno_livre.cpf, '')
        self.assertIsNone(self.aluno_livre.matricula)
        self.assertFalse(self.aluno_livre.ativo)

        # Usuário anonimizado e sem acesso
        self.user_livre.refresh_from_db()
        self.assertTrue(self.user_livre.username.startswith('anonimo-'))
        self.assertEqual(self.user_livre.email, '')
        self.assertFalse(self.user_livre.has_usable_password())
        self.assertFalse(
            self.client.login(username='alu_livre', password='x'),
        )

        # Auditoria registra a exclusão
        self.assertTrue(
            LogAuditoria.objects.filter(
                acao='exclusao', usuario=self.user_tec,
            ).exists(),
        )

    def test_anonimizacao_preserva_registros_de_pesquisa(self):
        """Bolsas e vínculos permanecem após a anonimização."""
        projeto_concluido = Projeto.objects.create(
            codigo='PV-SOL-C-2026', titulo='Projeto Concluído',
            data_registro=date(2024, 1, 1), data_inicio=date(2024, 2, 1),
            data_termino=date(2024, 12, 1),
            coordenador=self.docente, instituicao=None, status='concluido',
        )
        bolsa = Bolsa.objects.create(
            projeto=projeto_concluido, aluno=self.aluno_livre,
            modalidade=self.modalidade,
            data_inicio=date(2024, 3, 1), data_fim=date(2024, 11, 30),
            status='encerrada',
        )
        self._abrir('alu_livre', tipo='exclusao', descricao='anonimizar')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_livre)
        self.client.login(username='tec_sol', password='x')
        self.client.post(
            reverse('lgpd_solicitacao_tratar', args=[sol.pk]),
            {'status': 'concluida', 'justificativa': 'ok'},
        )
        # A bolsa continua existindo, apontando para a Pessoa anonimizada
        bolsa.refresh_from_db()
        self.aluno_livre.refresh_from_db()
        self.assertIn('anonimizado', bolsa.aluno.nome)
        self.assertEqual(
            SolicitacaoLGPD.objects.filter(
                titular__username__startswith='anonimo-',
            ).count(),
            1,
        )

    def test_tecnico_ve_vinculos_no_detalhe_da_exclusao(self):
        self._abrir('alu_bloq', tipo='exclusao', descricao='anonimizar')
        sol = SolicitacaoLGPD.objects.get(titular=self.user_bloq)
        self.client.login(username='tec_sol', password='x')
        resp = self.client.get(
            reverse('lgpd_solicitacao_detalhe', args=[sol.pk]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'bolsa ativa')
        self.assertContains(resp, 'Vínculos ativos')

    # ------------------------------------------------------------------
    # Página LGPD: acesso às solicitações e revogação de consentimento
    # ------------------------------------------------------------------

    def test_lgpd_pagina_oferece_solicitacoes_e_revogacao(self):
        self.client.login(username='alu_livre', password='x')
        resp = self.client.post(reverse('lgpd_consentimento'), follow=True)
        self.assertContains(resp, 'Minhas solicitações')
        self.assertContains(resp, 'Revogar consentimento')

    def test_revogar_consentimento(self):
        self.client.login(username='alu_livre', password='x')
        self.client.post(reverse('lgpd_consentimento'))
        perfil = Perfil.objects.get(user=self.user_livre)
        self.assertTrue(perfil.consentimento_lgpd)

        resp = self.client.post(
            reverse('lgpd_revogar_consentimento'), follow=True,
        )
        self.assertContains(resp, 'Consentimento revogado')
        perfil.refresh_from_db()
        self.assertFalse(perfil.consentimento_lgpd)
        self.assertIsNone(perfil.data_consentimento)

    def test_revogar_consentimento_exige_post(self):
        self.client.login(username='alu_livre', password='x')
        resp = self.client.get(reverse('lgpd_revogar_consentimento'))
        self.assertEqual(resp.status_code, 302)
        perfil = Perfil.objects.get(user=self.user_livre)
        self.assertFalse(perfil.consentimento_lgpd)
