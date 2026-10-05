"""Testes do módulo de Equipes (§3.8): permissões, CRUD e regras."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Instituicao, LogAuditoria, Perfil
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Pessoa, Projeto


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _dados_novo_membro(pessoa, **extras):
    dados = {
        'pessoa': pessoa.pk,
        'funcao': 'tecnico',
        'carga_horaria': '10',
        'data_entrada': '2026-03-01',
        'data_saida': '',
    }
    dados.update(extras)
    return dados


class EquipeTests(TestCase):
    """Permissões e operações do módulo de Equipes."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.coordenador = Pessoa.objects.create(
            nome='Coordenador Equipe', email='coord.eq@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.docente_fora = Pessoa.objects.create(
            nome='Docente Fora', email='fora.eq@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Equipe', email='aluno.eq@alunos.edu.br',
            tipo='aluno', matricula='20260201', instituicao=inst,
        )
        self.externa = Pessoa.objects.create(
            nome='Pessoa Externa', email='ext.eq@empresa.com',
            tipo='externo', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PV-EQ-2026', titulo='Projeto com equipe',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.coordenador, instituicao=inst,
        )
        self.membro = MembroEquipe.objects.create(
            projeto=self.projeto, pessoa=self.aluno, funcao='discente',
            data_entrada=date(2026, 3, 1),
        )

        _criar_usuario('alu_eq', Perfil.PERFIL_ALUNO, self.aluno)
        _criar_usuario('coord_eq', Perfil.PERFIL_DOCENTE, self.coordenador)
        _criar_usuario('fora_eq', Perfil.PERFIL_DOCENTE, self.docente_fora)
        _criar_usuario('tec_eq', Perfil.PERFIL_TECNICO)
        self.user_admin = User.objects.create_superuser('adm_eq', password='x')

    def _url_novo(self):
        return reverse('membro_novo', args=[self.projeto.pk])

    # ------------------------------------------------------------------
    # Permissões
    # ------------------------------------------------------------------

    def test_novo_exige_login(self):
        self.assertEqual(self.client.get(self._url_novo()).status_code, 302)

    def test_aluno_negado_mesmo_participando(self):
        self.client.login(username='alu_eq', password='x')
        self.assertEqual(self.client.get(self._url_novo()).status_code, 403)

    def test_docente_nao_coordenador_negado(self):
        self.client.login(username='fora_eq', password='x')
        self.assertEqual(self.client.get(self._url_novo()).status_code, 403)

    def test_coordenador_acessa_form(self):
        self.client.login(username='coord_eq', password='x')
        self.assertEqual(self.client.get(self._url_novo()).status_code, 200)

    def test_tecnico_acessa_form(self):
        self.client.login(username='tec_eq', password='x')
        self.assertEqual(self.client.get(self._url_novo()).status_code, 200)

    def test_superusuario_acessa_form(self):
        self.client.login(username='adm_eq', password='x')
        self.assertEqual(self.client.get(self._url_novo()).status_code, 200)

    def test_aluno_nao_encerra_vinculo(self):
        url = reverse('membro_encerrar', args=[self.membro.pk])
        self.client.login(username='alu_eq', password='x')
        self.assertEqual(self.client.post(url).status_code, 403)
        self.membro.refresh_from_db()
        self.assertTrue(self.membro.ativo)

    # ------------------------------------------------------------------
    # CRUD e regras
    # ------------------------------------------------------------------

    def test_coordenador_adiciona_membro(self):
        self.client.login(username='coord_eq', password='x')
        resp = self.client.post(self._url_novo(), _dados_novo_membro(self.externa))
        self.assertEqual(resp.status_code, 302)
        membro = MembroEquipe.objects.get(
            projeto=self.projeto, pessoa=self.externa, funcao='tecnico',
        )
        self.assertTrue(membro.ativo)
        self.assertIsNone(membro.data_saida)

    def test_saida_anterior_a_entrada_derro_form(self):
        self.client.login(username='tec_eq', password='x')
        resp = self.client.post(
            self._url_novo(),
            _dados_novo_membro(self.externa, data_saida='2026-02-01'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'não pode ser anterior')
        self.assertFalse(
            MembroEquipe.objects.filter(pessoa=self.externa).exists(),
        )

    def test_duplicidade_mesma_funcao_derro_form(self):
        self.client.login(username='tec_eq', password='x')
        resp = self.client.post(
            self._url_novo(),
            _dados_novo_membro(self.aluno, funcao='discente'),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'já integra a equipe')
        self.assertEqual(
            MembroEquipe.objects.filter(
                projeto=self.projeto, pessoa=self.aluno, funcao='discente',
            ).count(),
            1,
        )

    def test_pessoa_inativa_fora_do_form(self):
        self.externa.ativo = False
        self.externa.save()
        self.client.login(username='tec_eq', password='x')
        resp = self.client.get(self._url_novo())
        self.assertNotContains(resp, 'Pessoa Externa')

    def test_editar_atualiza_membro(self):
        self.client.login(username='coord_eq', password='x')
        url = reverse('membro_editar', args=[self.membro.pk])
        resp = self.client.post(url, {
            'pessoa': self.aluno.pk,
            'funcao': 'discente',
            'carga_horaria': '20',
            'data_entrada': '2026-03-01',
            'data_saida': '',
        })
        self.assertEqual(resp.status_code, 302)
        self.membro.refresh_from_db()
        self.assertEqual(self.membro.carga_horaria, 20)
        self.assertTrue(self.membro.ativo)

    def test_editar_com_saida_inativa(self):
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_editar', args=[self.membro.pk])
        self.client.post(url, {
            'pessoa': self.aluno.pk,
            'funcao': 'discente',
            'carga_horaria': '10',
            'data_entrada': '2026-03-01',
            'data_saida': '2026-06-01',
        })
        self.membro.refresh_from_db()
        self.assertEqual(self.membro.data_saida, date(2026, 6, 1))
        self.assertFalse(self.membro.ativo)

    def test_encerrar_vinculo_via_post(self):
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_encerrar', args=[self.membro.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.membro.refresh_from_db()
        self.assertFalse(self.membro.ativo)
        self.assertEqual(self.membro.data_saida, timezone.localdate())

    def test_encerrar_get_nao_altera(self):
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_encerrar', args=[self.membro.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        self.membro.refresh_from_db()
        self.assertTrue(self.membro.ativo)

    def test_excluir_membro_e_registra_auditoria(self):
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_excluir', args=[self.membro.pk])
        justificativa = 'Cadastro duplicado por erro de digitação.'
        resp = self.client.post(url, {'justificativa': justificativa})
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(MembroEquipe.objects.filter(pk=self.membro.pk).exists())
        log = LogAuditoria.objects.get(
            acao='exclusao',
            usuario__username='tec_eq',
            caminho__contains='/excluir/',
        )
        self.assertEqual(log.justificativa, justificativa)

    def test_excluir_sem_justificativa_nao_remove(self):
        """POST sem (ou com) justificativa vazia volta ao form com erro."""
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_excluir', args=[self.membro.pk])
        for dados in ({}, {'justificativa': '   '}):
            resp = self.client.post(url, dados)
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'Informe a justificativa')
        self.assertTrue(MembroEquipe.objects.filter(pk=self.membro.pk).exists())

    def test_excluir_get_mostra_confirmacao_e_nao_remove(self):
        """O GET abre a página de confirmação com justificativa obrigatória."""
        self.client.login(username='tec_eq', password='x')
        url = reverse('membro_excluir', args=[self.membro.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'justificativa')
        self.assertContains(resp, 'não pode ser desfeita')
        self.assertTrue(MembroEquipe.objects.filter(pk=self.membro.pk).exists())

    def test_aluno_negado_na_exclusao(self):
        """Aluno não vê nem confirma a exclusão (403, sem remoção)."""
        url = reverse('membro_excluir', args=[self.membro.pk])
        self.client.login(username='alu_eq', password='x')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(url, {'justificativa': 'x'}).status_code, 403,
        )
        self.assertTrue(MembroEquipe.objects.filter(pk=self.membro.pk).exists())

    # ------------------------------------------------------------------
    # Detalhe do projeto — botões conforme permissão
    # ------------------------------------------------------------------

    def test_detalhe_coordenador_ve_botoes(self):
        self.client.login(username='coord_eq', password='x')
        resp = self.client.get(reverse('projeto_detalhe', args=[self.projeto.pk]))
        self.assertContains(resp, 'Adicionar membro')
        self.assertContains(resp, 'Encerrar')

    def test_detalhe_aluno_nao_ve_botoes(self):
        self.client.login(username='alu_eq', password='x')
        resp = self.client.get(reverse('projeto_detalhe', args=[self.projeto.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Adicionar membro')

    def test_detalhe_lista_situacao_e_saida(self):
        self.client.login(username='tec_eq', password='x')
        resp = self.client.get(reverse('projeto_detalhe', args=[self.projeto.pk]))
        self.assertContains(resp, 'Ativo')
        self.assertContains(resp, 'Situação')
