"""Testes do módulo de Editais (views, permissões e fluxo de validação)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil
from apps.bolsas.models import ModalidadeBolsa

from apps.editais.models import Edital


def _criar_usuario(username, perfil):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil)
    return user


def _criar_edital(status='rascunho', **kwargs):
    dados = {
        'codigo': 'EDITAL-TESTE-01',
        'titulo': 'Edital de teste',
        'data_inicio': date(2026, 3, 1),
        'data_fim': date(2026, 6, 30),
        'status': status,
    }
    dados.update(kwargs)
    return Edital.objects.create(**dados)


class EditalAcessoTests(TestCase):
    """Testes de acesso às views de editais."""

    def setUp(self):
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.edital = _criar_edital(modalidade=self.modalidade)
        _criar_usuario('alu_edital', Perfil.PERFIL_ALUNO)
        _criar_usuario('doc_edital', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_edital', Perfil.PERFIL_TECNICO)
        _criar_usuario('dir_edital', Perfil.PERFIL_DIRETOR)

    def test_lista_exige_login(self):
        self.assertEqual(self.client.get(reverse('editais_lista')).status_code, 302)

    def test_aluno_lista_somente_visualizacao(self):
        self.client.login(username='alu_edital', password='x')
        response = self.client.get(reverse('editais_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'EDITAL-TESTE-01')
        self.assertNotContains(response, '+ Novo edital')
        self.assertNotContains(response, '>Editar<')

    def test_aluno_e_docente_nao_criam_nem_editam(self):
        for username in ('alu_edital', 'doc_edital'):
            self.client.login(username=username, password='x')
            self.assertEqual(self.client.get(reverse('edital_novo')).status_code, 403)
            self.assertEqual(
                self.client.get(
                    reverse('edital_editar', kwargs={'pk': self.edital.pk})
                ).status_code,
                403,
            )
            self.client.logout()

    def test_aluno_nao_ve_acoes_do_fluxo(self):
        self.client.login(username='alu_edital', password='x')
        response = self.client.get(
            reverse('edital_detalhe', kwargs={'pk': self.edital.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Publicar e validar')

    def test_tecnico_cria_edital_como_rascunho(self):
        """Técnico cria; status nasce rascunho e criado_por é registrado."""
        self.client.login(username='tec_edital', password='x')
        response = self.client.post(reverse('edital_novo'), {
            'codigo': 'NOVO-EDT-01',
            'titulo': 'Novo edital',
            'data_inicio': '2026-05-01',
            'data_fim': '2026-08-31',
            'modalidade': self.modalidade.pk,
            'nota_minima': '6.00',
        })
        self.assertEqual(response.status_code, 302)
        edital = Edital.objects.get(codigo='NOVO-EDT-01')
        self.assertEqual(edital.status, 'rascunho')
        self.assertEqual(edital.criado_por.username, 'tec_edital')

    def test_tecnico_edita_edital(self):
        self.client.login(username='tec_edital', password='x')
        response = self.client.get(
            reverse('edital_editar', kwargs={'pk': self.edital.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_data_fim_menor_que_inicio_e_rejeitada(self):
        self.client.login(username='tec_edital', password='x')
        response = self.client.post(reverse('edital_novo'), {
            'codigo': 'DTAS-ERR',
            'titulo': 'Datas inválidas',
            'data_inicio': '2026-08-31',
            'data_fim': '2026-05-01',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'posterior')
        self.assertFalse(Edital.objects.filter(codigo='DTAS-ERR').exists())


class FluxoEditalTests(TestCase):
    """Fluxo de vida: rascunho → publicado → em_andamento → encerrado.

    Publicação exige nível Diretor+ (o técnico propõe, o diretor valida).
    """

    def setUp(self):
        self.edital = _criar_edital()
        _criar_usuario('tec_fluxo', Perfil.PERFIL_TECNICO)
        _criar_usuario('dir_fluxo', Perfil.PERFIL_DIRETOR)
        _criar_usuario('alu_fluxo', Perfil.PERFIL_ALUNO)

    def _acao(self, usuario, acao, follow=False):
        self.client.login(username=usuario, password='x')
        return self.client.post(
            reverse('edital_acao', kwargs={'pk': self.edital.pk, 'acao': acao}),
            follow=follow,
        )

    def test_tecnico_nao_publica(self):
        """Técnico não valida a própria criação (requisito §3.1)."""
        response = self._acao('tec_fluxo', 'publicar')
        self.assertEqual(response.status_code, 403)
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'rascunho')

    def test_diretor_publica_com_carimbo_de_validacao(self):
        response = self._acao('dir_fluxo', 'publicar')
        self.assertEqual(response.status_code, 302)
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'publicado')
        self.assertEqual(self.edital.validado_por.username, 'dir_fluxo')
        self.assertIsNotNone(self.edital.data_validacao)

    def test_fluxo_completo_tecnico_opera_apos_publicacao(self):
        """publicado → iniciar → em_andamento → encerrar → encerrado."""
        self._acao('dir_fluxo', 'publicar')
        response = self._acao('tec_fluxo', 'iniciar')
        self.assertEqual(response.status_code, 302)
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'em_andamento')
        self._acao('tec_fluxo', 'encerrar')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'encerrado')

    def test_transicao_invalida_e_bloqueada_com_mensagem(self):
        """Não é possível iniciar um rascunho; status não muda."""
        response = self._acao('tec_fluxo', 'iniciar', follow=True)
        self.assertContains(response, 'Não é possível iniciar')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'rascunho')

    def test_acao_via_get_e_405(self):
        """Ações mudam estado: somente POST."""
        self.client.login(username='dir_fluxo', password='x')
        response = self.client.get(
            reverse('edital_acao', kwargs={'pk': self.edital.pk, 'acao': 'publicar'})
        )
        self.assertEqual(response.status_code, 405)

    def test_acao_desconhecida_e_bloqueada(self):
        response = self._acao('dir_fluxo', 'explodir')
        self.assertEqual(response.status_code, 403)

    def test_aluno_nao_executa_acoes(self):
        response = self._acao('alu_fluxo', 'publicar')
        self.assertEqual(response.status_code, 403)
        response = self._acao('alu_fluxo', 'cancelar')
        self.assertEqual(response.status_code, 403)
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'rascunho')

    def test_cancelar_e_permitido_para_tecnico(self):
        self._acao('dir_fluxo', 'publicar')
        self._acao('tec_fluxo', 'cancelar')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'cancelado')
