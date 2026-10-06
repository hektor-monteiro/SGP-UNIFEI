"""Testes da nota automática por financiamento externo (requisito §3.4).

Regra da UNIFEI: projeto com recursos externos > 0 recebe nota 10,00
automaticamente e dispensa a avaliação por pares. Ao remover (ou zerar)
os recursos externos o projeto volta para o fluxo de avaliação: se já
houver alocações, a nota é recalculada com elas; senão ele volta para
'não submetido'.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.editais.models import Avaliacao
from apps.editais.views import _recalcular_projeto
from apps.projetos.models import Pessoa, Projeto


def _criar_usuario(username, perfil, com_pessoa=True):
    """Cria usuário com Perfil e, opcionalmente, Pessoa vinculada."""
    user = User.objects.create_user(username, password='x')
    p = Perfil.objects.create(user=user, perfil=perfil)
    if com_pessoa:
        pessoa = Pessoa.objects.create(
            nome=username.title(),
            email=f'{username}@test.com',
            tipo='aluno' if perfil == Perfil.PERFIL_ALUNO else perfil,
        )
        p.pessoa = pessoa
        p.save()
    return user


class NotaAutomaticaModelTests(TestCase):
    """Regra de nota automática aplicada pelo model."""

    def setUp(self):
        hoje = localdate()
        self.docente = _criar_usuario('doc_nap', Perfil.PERFIL_DOCENTE)
        self.tecnico = _criar_usuario('tec_nap', Perfil.PERFIL_TECNICO)
        self.avaliador = _criar_usuario('doc_nap2', Perfil.PERFIL_DOCENTE)
        self.pessoa = self.docente.perfil.pessoa
        self.projeto = Projeto.objects.create(
            codigo='PVDI777-2026',
            titulo='Projeto sem financiamento externo',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=10),
            coordenador=self.pessoa,
        )

    def _criar_avaliacao_concluida(self, nota):
        """Aloca e conclui uma avaliação por pares no ORM."""
        return Avaliacao.objects.create(
            tipo='projeto',
            projeto=self.projeto,
            avaliador=self.avaliador,
            alocado_por=self.tecnico,
            status='concluida',
            nota=nota,
            parecer='Avaliação registrada no teste.',
        )

    def test_sem_recursos_externos_nao_recebe_nota(self):
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')
        self.assertIsNone(self.projeto.nota)
        self.assertFalse(self.projeto.nota_automatica)
        self.assertFalse(self.projeto.financiamento_externo)

    def test_com_recursos_externos_nasce_avaliado_com_nota_10(self):
        projeto = Projeto.objects.create(
            codigo='PVDI778-2026',
            titulo='Projeto com financiamento externo',
            data_registro=localdate(),
            data_inicio=localdate() - timedelta(days=10),
            coordenador=self.pessoa,
            recursos_externos=Decimal('120000.00'),
        )
        self.assertEqual(projeto.status_avaliacao, 'avaliada')
        self.assertEqual(projeto.nota, Decimal('10.00'))
        self.assertTrue(projeto.nota_automatica)
        self.assertTrue(projeto.financiamento_externo)

    def test_recursos_externos_zerados_contam_como_sem_financiamento(self):
        self.projeto.recursos_externos = Decimal('0.00')
        self.projeto.save()
        self.assertFalse(self.projeto.financiamento_externo)
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')

    def test_adicionar_recursos_externos_zera_avaliacao_por_pares(self):
        # Avaliação por pares concluída com nota 8,00
        self._criar_avaliacao_concluida(Decimal('8.00'))
        self.projeto.recalcular_avaliacao()
        self.projeto.save()
        self.assertEqual(self.projeto.nota, Decimal('8.00'))
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')

        # Financiamento externo passa a existir → nota 10,00 automática
        self.projeto.recursos_externos = Decimal('90000.00')
        self.projeto.save()
        self.assertEqual(self.projeto.nota, Decimal('10.00'))
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')
        self.assertTrue(self.projeto.nota_automatica)

    def test_remover_recursos_restaura_nota_das_avaliacoes(self):
        # Estado automático com uma alocação existente (por pares)
        self.projeto.recursos_externos = Decimal('90000.00')
        self.projeto.save()
        self._criar_avaliacao_concluida(Decimal('7.50'))

        self.projeto.recursos_externos = None
        self.projeto.save()
        self.assertFalse(self.projeto.nota_automatica)
        self.assertEqual(self.projeto.nota, Decimal('7.50'))
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')

    def test_remover_recursos_sem_avaliacoes_volta_para_nao_submetido(self):
        self.projeto.recursos_externos = Decimal('90000.00')
        self.projeto.save()
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')

        self.projeto.recursos_externos = None
        self.projeto.save()
        self.assertFalse(self.projeto.nota_automatica)
        self.assertIsNone(self.projeto.nota)
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')

    def test_recalcular_nao_sobrescreve_nota_automatica(self):
        self.projeto.recursos_externos = Decimal('90000.00')
        self.projeto.save()
        # Alocação criada diretamente no ORM não derruba a nota 10,00
        self._criar_avaliacao_concluida(Decimal('4.00'))
        _recalcular_projeto(self.projeto)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.nota, Decimal('10.00'))
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')
        self.assertTrue(self.projeto.nota_automatica)


class NotaAutomaticaViewTests(TestCase):
    """Interface: submissão dispensada, alocação bloqueada, nota exibida."""

    def setUp(self):
        hoje = localdate()
        self.docente = _criar_usuario('doc_nav', Perfil.PERFIL_DOCENTE)
        self.tecnico = _criar_usuario('tec_nav', Perfil.PERFIL_TECNICO)
        self.projeto = Projeto.objects.create(
            codigo='PVDI779-2026',
            titulo='Projeto financiado externamente',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=10),
            coordenador=self.docente.perfil.pessoa,
            recursos_externos=Decimal('75000.00'),
        )
        self.url_detalhe = reverse(
            'projeto_detalhe', kwargs={'pk': self.projeto.pk},
        )
        self.url_submeter = reverse(
            'projeto_submeter', kwargs={'pk': self.projeto.pk},
        )
        self.url_alocar = reverse(
            'projeto_alocar', kwargs={'pk': self.projeto.pk},
        )

    def test_detalhe_exibe_nota_automatica_e_oculta_botoes(self):
        self.client.login(username='tec_nav', password='x')
        response = self.client.get(self.url_detalhe)
        self.assertEqual(response.status_code, 200)
        # Origem da nota fica explícita para o usuário
        self.assertContains(response, '10,00')
        self.assertContains(
            response, 'a avaliação por pares é dispensada',
        )
        # Sem submissão nem alocação para projeto já avaliado
        self.assertNotContains(response, 'Enviar para avaliação por pares')
        self.assertNotContains(response, '+ Alocar avaliador')

    def test_submeter_projeto_com_financiamento_e_dispensado(self):
        self.client.login(username='doc_nav', password='x')
        response = self.client.post(self.url_submeter, follow=True)
        self.assertContains(response, 'avaliação por pares é dispensada')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')
        self.assertEqual(self.projeto.nota, Decimal('10.00'))
        self.assertEqual(Avaliacao.objects.filter(projeto=self.projeto).count(), 0)

    def test_alocacao_de_avaliador_e_bloqueada(self):
        outro = _criar_usuario('doc_nav2', Perfil.PERFIL_DOCENTE)
        self.client.login(username='tec_nav', password='x')
        response = self.client.post(
            self.url_alocar, {'avaliador': outro.pk}, follow=True,
        )
        # Mensagem clara e nenhuma alocação criada; nota segue automática
        self.assertContains(response, 'não recebe avaliação por pares')
        self.assertEqual(Avaliacao.objects.filter(projeto=self.projeto).count(), 0)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.nota, Decimal('10.00'))
        self.assertTrue(self.projeto.nota_automatica)

    def test_coordenador_nao_ve_botao_de_envio(self):
        self.client.login(username='doc_nav', password='x')
        response = self.client.get(self.url_detalhe)
        self.assertNotContains(response, 'Enviar para avaliação por pares')

    def test_painel_nao_lista_para_alocacao_quem_ja_tem_nota_automatica(self):
        """Na fila "Aguardando alocação" só entram projetos a avaliar."""
        hoje = localdate()
        sem_financiamento = Projeto.objects.create(
            codigo='PVDI781-2026',
            titulo='Projeto aguardando avaliação por pares',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=10),
            coordenador=self.docente.perfil.pessoa,
            status_avaliacao='submetido',
        )
        self.client.login(username='tec_nav', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Aguardando alocação de avaliador')
        # Quem precisa de avaliador aparece; o financiado externamente não
        self.assertContains(response, sem_financiamento.codigo)
        self.assertNotContains(response, self.projeto.codigo)
