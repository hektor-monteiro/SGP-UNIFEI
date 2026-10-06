"""Testes da avaliação por pares de projetos (requisito §3.4).

Fluxo: o coordenador envia o projeto para avaliação → o técnico aloca
docentes (paridade: a equipe não avalia o próprio projeto) → o avaliador
preenche notas por critério de escopo 'projeto' → a nota final (média)
é exibida como indicador na alocação de bolsas (§3.5).
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.bolsas.models import Indicacao, ModalidadeBolsa
from apps.editais.models import Avaliacao, CriterioAvaliacao, Edital
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Pessoa, Projeto, Proposta
from sgp.tests.arquivos_teste import MediaTemporariaMixin, anexar_pdf


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


class BaseAvaliacaoProjetoTests(MediaTemporariaMixin, TestCase):
    """Fixtures comuns: projeto coordenado pelo docente, equipe e usuários."""

    def setUp(self):
        super().setUp()
        hoje = localdate()
        self.docente_coord = _criar_usuario('doc_avp', Perfil.PERFIL_DOCENTE)
        self.docente_fora = _criar_usuario('doc_avp2', Perfil.PERFIL_DOCENTE)
        self.tecnico = _criar_usuario('tec_avp', Perfil.PERFIL_TECNICO)
        self.aluno = _criar_usuario('alu_avp', Perfil.PERFIL_ALUNO)

        self.pessoa_coord = self.docente_coord.perfil.pessoa
        self.pessoa_fora = self.docente_fora.perfil.pessoa

        self.projeto = Projeto.objects.create(
            codigo='PVDI999-2026',
            titulo='Projeto da avaliação por pares',
            resumo='Projeto submetido à avaliação por pares de docentes.',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=30),
            coordenador=self.pessoa_coord,
        )
        # Documento em PDF é exigido na submissão para avaliação (§3.1)
        anexar_pdf(self.projeto)
        # Membro da equipe: não pode ser alocado como avaliador
        self.membro = Pessoa.objects.create(
            nome='Membro da Equipe', email='membro@avp.test', tipo='aluno',
        )
        MembroEquipe.objects.create(
            projeto=self.projeto,
            pessoa=self.membro,
            funcao='discente',
            data_entrada=hoje,
        )

        self.url_submeter = reverse(
            'projeto_submeter', kwargs={'pk': self.projeto.pk},
        )
        self.url_alocar = reverse(
            'projeto_alocar', kwargs={'pk': self.projeto.pk},
        )

    def _submeter(self, usuario='tec_avp'):
        """Envia o projeto para avaliação (via técnico) e retorna a URL."""
        self.client.login(username=usuario, password='x')
        response = self.client.post(self.url_submeter)
        self.client.logout()
        return response

    def _alocar(self, avaliador):
        """Aloca um avaliador direto no ORM (estado 'alocada')."""
        return Avaliacao.objects.create(
            tipo='projeto',
            projeto=self.projeto,
            avaliador=avaliador,
            alocado_por=User.objects.get(username='tec_avp'),
            status='alocada',
        )


class SubmissaoProjetoTests(BaseAvaliacaoProjetoTests):
    """Envio do projeto para avaliação por pares (botão do coordenador)."""

    def test_coordenador_envia_para_avaliacao(self):
        self.client.login(username='doc_avp', password='x')
        response = self.client.post(self.url_submeter, follow=True)
        self.assertContains(response, 'enviado para avaliação por pares')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')

    def test_tecnico_tambem_envia(self):
        self._submeter()
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')

    def test_docente_de_fora_e_aluno_nao_enviam(self):
        for username in ('doc_avp2', 'alu_avp'):
            self.client.login(username=username, password='x')
            self.assertEqual(self.client.post(self.url_submeter).status_code, 403)
            self.client.logout()
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')

    def test_get_nao_altera_o_projeto(self):
        """Somente POST (o envio é uma ação explícita)."""
        self.client.login(username='doc_avp', password='x')
        self.assertEqual(self.client.get(self.url_submeter).status_code, 405)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')

    def test_reenvio_e_bloqueado(self):
        self._submeter()
        self.client.login(username='doc_avp', password='x')
        response = self.client.post(self.url_submeter, follow=True)
        self.assertContains(response, 'já foi enviado')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')

    def test_botao_visivel_apenas_quem_pode_enviar(self):
        url_detalhe = reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk})
        self.client.login(username='doc_avp', password='x')
        response = self.client.get(url_detalhe)
        self.assertContains(response, 'Enviar para avaliação por pares')
        self.client.logout()

        # Docente de fora vê o detalhe, mas não tem o botão de envio
        self.client.login(username='doc_avp2', password='x')
        response = self.client.get(url_detalhe)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Enviar para avaliação por pares')


class AlocacaoProjetoTests(BaseAvaliacaoProjetoTests):
    """Alocação de docentes avaliadores (somente técnico+)."""

    def setUp(self):
        super().setUp()
        self._submeter()

    def test_tecnico_aloca_avaliador(self):
        self.client.login(username='tec_avp', password='x')
        response = self.client.post(
            self.url_alocar, {'avaliador': str(self.docente_fora.pk)},
        )
        self.assertEqual(response.status_code, 302)
        avaliacao = Avaliacao.objects.get(projeto=self.projeto)
        self.assertEqual(avaliacao.tipo, 'projeto')
        self.assertEqual(avaliacao.avaliador, self.docente_fora)
        self.assertEqual(avaliacao.status, 'alocada')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'em_avaliacao')

    def test_docente_nao_aloca(self):
        self.client.login(username='doc_avp', password='x')
        response = self.client.post(
            self.url_alocar, {'avaliador': str(self.docente_fora.pk)},
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Avaliacao.objects.filter(projeto=self.projeto).exists())

    def test_alocacao_antes_do_envio_e_bloqueada(self):
        self.projeto.status_avaliacao = 'nao_submetido'
        self.projeto.save()
        self.client.login(username='tec_avp', password='x')
        response = self.client.post(
            self.url_alocar,
            {'avaliador': str(self.docente_fora.pk)},
            follow=True,
        )
        self.assertContains(response, 'não foi enviado para avaliação')
        self.assertFalse(Avaliacao.objects.filter(projeto=self.projeto).exists())

    def test_equipe_excluida_da_lista_de_avaliadores(self):
        """Paridade: coordenador e membros não avaliam o próprio projeto."""
        self.client.login(username='tec_avp', password='x')
        response = self.client.get(self.url_alocar)
        self.assertEqual(response.status_code, 200)
        queryset = response.context['form'].fields['avaliador'].queryset
        self.assertIn(self.docente_fora, queryset)
        self.assertNotIn(self.docente_coord, queryset)

    def test_avaliador_duplicado_e_rejeitado(self):
        self._alocar(self.docente_fora)
        self.client.login(username='tec_avp', password='x')
        response = self.client.post(
            self.url_alocar,
            {'avaliador': str(self.docente_fora.pk)},
            follow=True,
        )
        self.assertContains(response, 'já está alocado')
        self.assertEqual(
            Avaliacao.objects.filter(projeto=self.projeto).count(), 1,
        )


class PreenchimentoProjetoTests(BaseAvaliacaoProjetoTests):
    """Notas por critério de escopo 'projeto' e cálculo da nota final."""

    def setUp(self):
        super().setUp()
        self._submeter()
        self.criterio_projeto = CriterioAvaliacao.objects.create(
            nome='Impacto do projeto', escopo='projeto', peso=3,
        )
        self.criterio_ambos = CriterioAvaliacao.objects.create(
            nome='Viabilidade geral', escopo='ambos', peso=1,
        )
        self.criterio_proposta = CriterioAvaliacao.objects.create(
            nome='Só para propostas', escopo='proposta', peso=5,
        )
        self.avaliacao = self._alocar(self.docente_fora)
        self.url = reverse(
            'avaliacao_detalhe', kwargs={'pk': self.avaliacao.pk},
        )

    def _post_notas(self, nota_projeto='8', nota_ambos='6', parecer='Ok.'):
        return self.client.post(self.url, {
            f'nota_{self.criterio_projeto.pk}': nota_projeto,
            f'nota_{self.criterio_ambos.pk}': nota_ambos,
            'parecer': parecer,
        })

    def test_apenas_criterios_do_escopo_do_projeto(self):
        self.client.login(username='doc_avp2', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Impacto do projeto')
        self.assertContains(response, 'Viabilidade geral')
        self.assertNotContains(response, 'Só para propostas')

    def test_avaliador_conclui_e_calcula_media_ponderada(self):
        self.client.login(username='doc_avp2', password='x')
        response = self._post_notas(nota_projeto='8', nota_ambos='6')
        self.assertEqual(response.status_code, 302)
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'concluida')
        # (8×3 + 6×1) / 4 = 7.50
        self.assertEqual(str(self.avaliacao.nota), '7.50')
        self.projeto.refresh_from_db()
        self.assertEqual(str(self.projeto.nota), '7.50')
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')

    def test_banca_com_dois_avaliadores_gera_media_final(self):
        terceiro = _criar_usuario('doc_avp3', Perfil.PERFIL_DOCENTE)
        segunda = self._alocar(terceiro)
        self.client.login(username='doc_avp2', password='x')
        self._post_notas(nota_projeto='8', nota_ambos='6')  # → 7.50
        self.client.logout()
        self.client.login(username='doc_avp3', password='x')
        response = self.client.post(
            reverse('avaliacao_detalhe', kwargs={'pk': segunda.pk}),
            {
                f'nota_{self.criterio_projeto.pk}': '4',
                f'nota_{self.criterio_ambos.pk}': '4',
                'parecer': 'Regular.',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.projeto.refresh_from_db()
        # média simples das concluídas: (7.50 + 4.00) / 2 = 5.75
        self.assertEqual(str(self.projeto.nota), '5.75')
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')

    def test_nao_avaliador_nao_envia_notas(self):
        self.client.login(username='doc_avp', password='x')
        response = self.client.post(self.url, {
            f'nota_{self.criterio_projeto.pk}': '10',
            f'nota_{self.criterio_ambos.pk}': '10',
            'parecer': 'Tentativa indevida.',
        })
        self.assertEqual(response.status_code, 403)
        self.avaliacao.refresh_from_db()
        self.assertEqual(self.avaliacao.status, 'alocada')

    def test_painel_do_avaliador_mostra_avaliacao_de_projeto(self):
        self.client.login(username='doc_avp2', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Avaliações a realizar')
        # Coluna "Objeto avaliado": Projeto - <código do projeto>
        self.assertContains(response, f'Projeto - {self.projeto.codigo}')
        self.assertContains(response, self.projeto.codigo)


class PainelAlocacaoProjetoTests(BaseAvaliacaoProjetoTests):
    """Seção "Aguardando alocação" do painel do técnico (§3.4)."""

    def test_tecnico_lista_projeto_submetido_com_acao_alocar_avaliador(self):
        self._submeter()
        self.client.login(username='tec_avp', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Aguardando alocação de avaliador')
        # Coluna "Objeto a avaliar": Projeto - <código do projeto>
        self.assertContains(response, f'Projeto - {self.projeto.codigo}')
        self.assertContains(response, 'Alocar Avaliador')
        self.assertContains(
            response,
            reverse('projeto_alocar', kwargs={'pk': self.projeto.pk}),
        )

    def test_projeto_com_avaliador_alocado_nao_lista(self):
        """Com alocação o projeto sai da fila (já tem avaliador)."""
        self._submeter()
        self.client.login(username='tec_avp', password='x')
        self.client.post(
            self.url_alocar, {'avaliador': str(self.docente_fora.pk)},
        )
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Aguardando alocação de avaliador')
        self.assertNotContains(response, 'Alocar Avaliador')

    def test_projeto_nao_submetido_nao_lista(self):
        """Antes do envio não há o que alocar."""
        self.client.login(username='tec_avp', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Aguardando alocação de avaliador')

    def test_docente_nao_ve_a_secao_de_alocacao(self):
        """A ação de alocação é exclusiva de técnico+ (e superusuário)."""
        self._submeter()
        self.client.login(username='doc_avp', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Aguardando alocação de avaliador')
        self.assertNotContains(response, 'Alocar Avaliador')


class RemocaoProjetoTests(BaseAvaliacaoProjetoTests):
    """Remoção de alocação recalcula status e nota do projeto."""

    def setUp(self):
        super().setUp()
        CriterioAvaliacao.objects.create(
            nome='Impacto do projeto remocao', escopo='projeto', peso=1,
        )

    def test_remover_unica_alocacao_volta_para_submetido(self):
        self._submeter()
        avaliacao = self._alocar(self.docente_fora)
        self.client.login(username='tec_avp', password='x')
        response = self.client.post(
            reverse('avaliacao_remover', kwargs={'pk': avaliacao.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Avaliacao.objects.filter(projeto=self.projeto).exists())
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')
        self.assertIsNone(self.projeto.nota)

    def test_remover_concluida_apaga_nota_e_volta_para_submetido(self):
        """Fluxo completo: alocar → concluir → remover."""
        self._submeter()
        self.client.login(username='tec_avp', password='x')
        self.client.post(
            self.url_alocar, {'avaliador': str(self.docente_fora.pk)},
        )
        self.client.logout()

        avaliacao = Avaliacao.objects.get(projeto=self.projeto)
        self.client.login(username='doc_avp2', password='x')
        self.client.post(
            reverse('avaliacao_detalhe', kwargs={'pk': avaliacao.pk}),
            {
                f'nota_{CriterioAvaliacao.objects.get(nome="Impacto do projeto remocao").pk}': '8',
                'parecer': 'Concluída.',
            },
        )
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'avaliada')
        self.assertEqual(str(self.projeto.nota), '8.00')
        self.client.logout()

        self.client.login(username='tec_avp', password='x')
        self.client.post(
            reverse('avaliacao_remover', kwargs={'pk': avaliacao.pk}),
        )
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')
        self.assertIsNone(self.projeto.nota)


class IndicadorNotaTests(TestCase):
    """A nota do projeto alimenta as telas de alocação de bolsas (§3.5)."""

    def setUp(self):
        hoje = localdate()
        self.tecnico = _criar_usuario('tec_ind', Perfil.PERFIL_TECNICO)
        self.docente = _criar_usuario('doc_ind', Perfil.PERFIL_DOCENTE)
        self.aluno = _criar_usuario('alu_ind', Perfil.PERFIL_ALUNO)
        self.modalidade = ModalidadeBolsa.objects.create(
            sigla='PIBIC', nome='Iniciação Científica',
        )
        self.edital = Edital.objects.create(
            codigo='EDITAL-IND-01',
            titulo='Edital do indicador',
            data_inicio=hoje - timedelta(days=5),
            data_fim=hoje + timedelta(days=30),
            status='em_andamento',
            modalidade=self.modalidade,
        )
        pessoa_doc = self.docente.perfil.pessoa
        self.projeto_nota = Projeto.objects.create(
            codigo='PVDI100-2026',
            titulo='Projeto com nota',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=10),
            coordenador=pessoa_doc,
            status_avaliacao='avaliada',
            nota='9.20',
        )
        self.proposta = Proposta.objects.create(
            titulo='Proposta indicador',
            edital=self.edital,
            projeto=self.projeto_nota,
            cotas=2,
            submetido_por=pessoa_doc,
            status='aprovada',
        )

    def test_detalhe_da_proposta_exibe_nota_do_projeto(self):
        self.client.login(username='tec_ind', password='x')
        response = self.client.get(
            reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk}),
        )
        self.assertContains(response, 'Nota do projeto (avaliação por pares)')
        # O template localiza o decimal (pt-BR): vírgula decimal
        self.assertContains(response, '9,20')

    def test_tela_de_indicacao_exibe_indicadores(self):
        self.client.login(username='doc_ind', password='x')
        response = self.client.get(
            reverse('proposta_indicar', kwargs={'pk': self.proposta.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Indicadores')
        self.assertContains(response, '9,20')

    def test_fila_ordena_pendentes_por_nota_do_projeto(self):
        # Segunda proposta com nota menor e uma sem nota
        pessoa_doc = self.docente.perfil.pessoa
        projeto_medio = Projeto.objects.create(
            codigo='PVDI101-2026',
            titulo='Projeto nota média',
            data_registro=localdate(),
            data_inicio=localdate() - timedelta(days=10),
            coordenador=pessoa_doc,
            status_avaliacao='avaliada',
            nota='5.00',
        )
        projeto_sem_nota = Projeto.objects.create(
            codigo='PVDI102-2026',
            titulo='Projeto sem nota',
            data_registro=localdate(),
            data_inicio=localdate() - timedelta(days=10),
            coordenador=pessoa_doc,
        )
        proposta_media = Proposta.objects.create(
            titulo='Proposta nota média',
            edital=self.edital,
            projeto=projeto_medio,
            cotas=1,
            submetido_por=pessoa_doc,
            status='aprovada',
        )
        proposta_sem_nota = Proposta.objects.create(
            titulo='Proposta sem nota',
            edital=self.edital,
            projeto=projeto_sem_nota,
            cotas=1,
            submetido_por=pessoa_doc,
            status='aprovada',
        )
        aluno_livre = Pessoa.objects.create(
            nome='Aluno Indicador', email='alunoidx@alu.test', tipo='aluno',
        )
        for proposta in (self.proposta, proposta_media, proposta_sem_nota):
            Indicacao.objects.create(
                proposta=proposta,
                aluno=aluno_livre,
                indicado_por=pessoa_doc,
            )

        self.client.login(username='tec_ind', password='x')
        response = self.client.get(reverse('indicacoes_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nota do projeto')
        fila = list(response.context['indicacoes'])
        # pendentes primeiro, depois maior nota (nulas por último)
        notas = [
            ind.proposta.projeto.nota if ind.proposta.projeto else None
            for ind in fila
        ]
        self.assertEqual([str(n) for n in notas[:2]], ['9.20', '5.00'])
        self.assertIsNone(notas[2])

    def test_pagina_de_implementacao_exibe_nota(self):
        indicacao = Indicacao.objects.create(
            proposta=self.proposta,
            aluno=self.aluno.perfil.pessoa,
            indicado_por=self.docente.perfil.pessoa,
        )
        self.client.login(username='tec_ind', password='x')
        response = self.client.get(
            reverse('indicacao_implementar', kwargs={'pk': indicacao.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nota da avaliação por pares')
        self.assertContains(response, '9,20')
