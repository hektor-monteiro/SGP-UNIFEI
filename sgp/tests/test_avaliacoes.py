"""Testes da avaliação de propostas: critérios, alocação e média ponderada."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.editais.models import (
    Avaliacao,
    CriterioAvaliacao,
    Edital,
    NotaCriterio,
)
from apps.projetos.models import Pessoa, Proposta


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


def _criar_edital(**kwargs):
    """Cria edital em andamento e vigente, a menos que informado o contrário."""
    hoje = localdate()
    dados = {
        'codigo': 'EDITAL-AVAL',
        'titulo': 'Edital de avaliação',
        'data_inicio': hoje - timedelta(days=10),
        'data_fim': hoje + timedelta(days=20),
        'status': 'em_andamento',
    }
    dados.update(kwargs)
    return Edital.objects.create(**dados)


def _criar_proposta(edital, submetido_por, titulo='Proposta de pesquisa'):
    return Proposta.objects.create(
        titulo=titulo,
        edital=edital,
        submetido_por=submetido_por,
    )


class CriterioAvaliacaoTests(TestCase):
    """CRUD de critérios de avaliação (gestão exclusiva do técnico+)."""

    def setUp(self):
        _criar_usuario('alu_crit', Perfil.PERFIL_ALUNO)
        _criar_usuario('doc_crit', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_crit', Perfil.PERFIL_TECNICO)

    def test_tecnico_cria_criterio_com_peso(self):
        self.client.login(username='tec_crit', password='x')
        response = self.client.post(reverse('criterio_novo'), {
            'nome': 'Relevância do tema',
            'descricao': 'Contribuição para a área.',
            'peso': '2.50',
            'ativo': 'on',
        })
        self.assertEqual(response.status_code, 302)
        criterio = CriterioAvaliacao.objects.get(nome='Relevância do tema')
        self.assertEqual(criterio.peso, Decimal('2.50'))
        self.assertTrue(criterio.ativo)

    def test_criterio_com_peso_invalido_e_rejeitado(self):
        self.client.login(username='tec_crit', password='x')
        response = self.client.post(reverse('criterio_novo'), {
            'nome': 'Peso zero',
            'peso': '0',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'maior que zero')
        self.assertFalse(CriterioAvaliacao.objects.filter(nome='Peso zero').exists())

    def test_aluno_e_docente_nao_gerenciam_criterios(self):
        for username in ('alu_crit', 'doc_crit'):
            self.client.login(username=username, password='x')
            self.assertEqual(self.client.get(reverse('criterio_novo')).status_code, 403)
            self.client.logout()

    def test_lista_visivel_a_todos_com_botoes_apenas_para_gerentes(self):
        CriterioAvaliacao.objects.create(nome='Metodologia', peso=3)

        self.client.login(username='alu_crit', password='x')
        response = self.client.get(reverse('criterios_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Metodologia')
        self.assertNotContains(response, '+ Novo critério')

        self.client.logout()
        self.client.login(username='tec_crit', password='x')
        response = self.client.get(reverse('criterios_lista'))
        self.assertContains(response, '+ Novo critério')


class AlocacaoTests(TestCase):
    """Alocação/remoção de avaliadores (técnicos e perfis superiores)."""

    def setUp(self):
        self.edital = _criar_edital()
        self.aluno = _criar_usuario('alu_aloc', Perfil.PERFIL_ALUNO)
        self.docente1 = _criar_usuario('doc_aloc1', Perfil.PERFIL_DOCENTE)
        self.docente2 = _criar_usuario('doc_aloc2', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_aloc', Perfil.PERFIL_TECNICO)
        self.proposta = _criar_proposta(
            self.edital, self.aluno.perfil.pessoa,
            titulo='Proposta para alocação',
        )
        self.url = reverse('proposta_alocar', kwargs={'pk': self.proposta.pk})

    def test_tecnico_aloca_docente_e_proposta_entra_em_avaliacao(self):
        self.client.login(username='tec_aloc', password='x')
        response = self.client.post(self.url, {'avaliador': self.docente1.pk})
        self.assertEqual(response.status_code, 302)
        avaliacao = Avaliacao.objects.get(proposta=self.proposta)
        self.assertEqual(avaliacao.avaliador, self.docente1)
        self.assertEqual(avaliacao.alocado_por.username, 'tec_aloc')
        self.assertEqual(avaliacao.status, 'alocada')
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.status, 'em_avaliacao')

    def test_aluno_e_docente_nao_alocam(self):
        for username in ('alu_aloc', 'doc_aloc1'):
            self.client.login(username=username, password='x')
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.client.logout()

    def test_alocacao_duplicada_e_bloqueada(self):
        self.client.login(username='tec_aloc', password='x')
        self.client.post(self.url, {'avaliador': self.docente1.pk})
        response = self.client.post(self.url, {'avaliador': self.docente1.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já está alocado')
        self.assertEqual(
            Avaliacao.objects.filter(proposta=self.proposta).count(), 1,
        )

    def test_apenas_docentes_sao_avaliadores(self):
        """O campo avaliador só aceita usuários com perfil docente."""
        self.client.login(username='tec_aloc', password='x')
        response = self.client.post(self.url, {'avaliador': self.aluno.pk})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Avaliacao.objects.filter(proposta=self.proposta).exists())

    def test_gerente_remove_alocacao_e_proposta_reverte(self):
        self.client.login(username='tec_aloc', password='x')
        self.client.post(self.url, {'avaliador': self.docente1.pk})
        avaliacao = Avaliacao.objects.get(proposta=self.proposta)
        response = self.client.post(
            reverse('avaliacao_remover', kwargs={'pk': avaliacao.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Avaliacao.objects.filter(proposta=self.proposta).exists())
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.status, 'submetida')

    def test_avaliador_alocado_acessa_proposta(self):
        self.client.login(username='tec_aloc', password='x')
        self.client.post(self.url, {'avaliador': self.docente1.pk})
        self.client.logout()

        url = reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        self.client.login(username='doc_aloc1', password='x')
        self.assertEqual(self.client.get(url).status_code, 200)


class AvaliacaoConclusaoTests(TestCase):
    """Notas por critério, média ponderada e aprovação automática."""

    def setUp(self):
        self.edital = _criar_edital()
        self.aluno = _criar_usuario('alu_aval', Perfil.PERFIL_ALUNO)
        self.docente = _criar_usuario('doc_aval', Perfil.PERFIL_DOCENTE)
        self.docente2 = _criar_usuario('doc_aval2', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_aval', Perfil.PERFIL_TECNICO)
        self.proposta = _criar_proposta(
            self.edital, self.aluno.perfil.pessoa,
            titulo='Proposta banca',
        )
        self.criterio_a = CriterioAvaliacao.objects.create(
            nome='Relevância', peso=3,
        )
        self.criterio_b = CriterioAvaliacao.objects.create(
            nome='Metodologia', peso=1,
        )
        self.avaliacao = Avaliacao.objects.create(
            tipo='proposta',
            proposta=self.proposta,
            avaliador=self.docente,
            alocado_por=User.objects.get(username='tec_aval'),
            status='alocada',
        )
        self.proposta.status = 'em_avaliacao'
        self.proposta.save()
        self.url = reverse('avaliacao_detalhe', kwargs={'pk': self.avaliacao.pk})

    def _post_notas(self, nota_a, nota_b, parecer='Parecer de teste.'):
        return self.client.post(self.url, {
            f'nota_{self.criterio_a.pk}': nota_a,
            f'nota_{self.criterio_b.pk}': nota_b,
            'parecer': parecer,
        })

    def test_edital_oculto_aparece_sem_link_para_avaliador(self):
        """Docente avaliador (abaixo de técnicos) vê o edital só como texto."""
        self.edital.status = 'encerrado'
        self.edital.save()
        self.client.login(username='doc_aval', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.edital.codigo)
        self.assertNotContains(
            response,
            reverse('edital_detalhe', kwargs={'pk': self.edital.pk}),
        )

    def test_painel_docente_mostra_proposta_pendente_com_link(self):
        self.client.login(username='doc_aval', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Propostas a avaliar')
        self.assertContains(response, 'Proposta banca')
        self.assertContains(response, 'Realizar avaliação')

    def test_conclusao_calcula_media_ponderada_e_aprova(self):
        """(8×3 + 4×1) / 4 = 7,00 ≥ 6,00 → proposta aprovada."""
        self.client.login(username='doc_aval', password='x')
        response = self._post_notas('8', '4', parecer='Bom tema, método adequado.')
        self.assertEqual(response.status_code, 302)

        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'concluida')
        self.assertEqual(self.avaliacao.nota, Decimal('7.00'))
        self.assertEqual(self.avaliacao.parecer, 'Bom tema, método adequado.')
        self.assertIsNotNone(self.avaliacao.data_conclusao)
        self.assertEqual(NotaCriterio.objects.filter(avaliacao=self.avaliacao).count(), 2)

        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.nota_final, Decimal('7.00'))
        self.assertEqual(self.proposta.status, 'aprovada')

    def test_nota_fora_de_0_a_10_e_rejeitada(self):
        self.client.login(username='doc_aval', password='x')
        response = self._post_notas('11', '5')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'menor ou igual a 10')
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'alocada')
        self.assertIsNone(self.avaliacao.nota)
        self.assertEqual(NotaCriterio.objects.count(), 0)

    def test_nota_faltando_criterio_e_rejeitada(self):
        self.client.login(username='doc_aval', password='x')
        response = self.client.post(self.url, {
            f'nota_{self.criterio_a.pk}': '7',
            'parecer': 'Sem nota do segundo critério.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'obrigatório')
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'alocada')

    def test_somente_o_avaliador_preenche_o_gerente_so_ve(self):
        # Aluno (estranho) não acessa
        self.client.login(username='alu_aval', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self._post_notas('8', '8').status_code, 403)
        self.client.logout()

        # Gerente visualiza, mas não preenche
        self.client.login(username='tec_aval', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self._post_notas('8', '8').status_code, 403)
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'alocada')

    def test_banca_com_multiplas_avaliacoes_e_realocacao(self):
        """Duas avaliações: em andamento → reprovada → realocação reverte."""
        avaliador2 = self.docente2
        Avaliacao.objects.create(
            tipo='proposta',
            proposta=self.proposta,
            avaliador=avaliador2,
            alocado_por=User.objects.get(username='tec_aval'),
            status='alocada',
        )

        # Primeira avaliação concluída: ainda em avaliação (falta a segunda)
        self.client.login(username='doc_aval', password='x')
        self._post_notas('8', '4')
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.status, 'em_avaliacao')
        self.client.logout()

        # Segunda avaliação concluída: média (7,00 + 4,00)/2 = 5,50 < 6 → reprovada
        av2 = Avaliacao.objects.get(avaliador=avaliador2)
        self.client.login(username='doc_aval2', password='x')
        self.client.post(
            reverse('avaliacao_detalhe', kwargs={'pk': av2.pk}),
            {
                f'nota_{self.criterio_a.pk}': '4',
                f'nota_{self.criterio_b.pk}': '4',
                'parecer': 'Abaixo do esperado.',
            },
        )
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.nota_final, Decimal('5.50'))
        self.assertEqual(self.proposta.status, 'reprovada')
        self.client.logout()

        # Realocação: remove a avaliação inadequada → 7,00 ≥ 6 → aprovada
        self.client.login(username='tec_aval', password='x')
        self.client.post(reverse('avaliacao_remover', kwargs={'pk': av2.pk}))
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.nota_final, Decimal('7.00'))
        self.assertEqual(self.proposta.status, 'aprovada')

    def test_tecnico_ajusta_nota_minima_do_edital(self):
        self.client.login(username='tec_aval', password='x')
        url = reverse('edital_editar', kwargs={'pk': self.edital.pk})
        response = self.client.get(url)
        self.assertContains(response, 'Nota mínima para aprovação')

        response = self.client.post(url, {
            'codigo': self.edital.codigo,
            'titulo': self.edital.titulo,
            'data_inicio': self.edital.data_inicio.isoformat(),
            'data_fim': self.edital.data_fim.isoformat(),
            'nota_minima': '8.00',
        })
        self.assertEqual(response.status_code, 302)
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.nota_minima, Decimal('8.00'))
