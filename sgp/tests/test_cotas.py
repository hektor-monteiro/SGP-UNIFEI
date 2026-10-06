"""Testes do fluxo de cotas de bolsa (requisito §3.5).

Ciclo: docente submete proposta com cotas → avaliação aprova → docente
indica os alunos → técnico implementa a bolsa.
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.bolsas.models import Bolsa, Indicacao, ModalidadeBolsa
from apps.editais.models import Edital
from apps.projetos.models import Pessoa, Projeto, Proposta


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


class BaseCotasTests(TestCase):
    """Fixtures comuns: edital em andamento, proposta aprovada e cotas."""

    def setUp(self):
        self.modalidade = ModalidadeBolsa.objects.create(
            sigla='PIBIC', nome='Iniciação Científica',
        )
        hoje = localdate()
        self.hoje = hoje
        self.edital = Edital.objects.create(
            codigo='EDITAL-COTAS-01',
            titulo='Edital de cotas de teste',
            data_inicio=hoje - timedelta(days=5),
            data_fim=hoje + timedelta(days=30),
            status='em_andamento',
            modalidade=self.modalidade,
        )
        self.docente = _criar_usuario('doc_cotas', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_cotas', Perfil.PERFIL_TECNICO)
        _criar_usuario('doc_fora_cotas', Perfil.PERFIL_DOCENTE)
        _criar_usuario('alu_cotas', Perfil.PERFIL_ALUNO)
        self.pessoa_docente = self.docente.perfil.pessoa
        self.projeto = Projeto.objects.create(
            codigo='PROJ-COTAS-01',
            titulo='Projeto das cotas',
            data_registro=hoje,
            data_inicio=hoje - timedelta(days=30),
            coordenador=self.pessoa_docente,
        )
        self.proposta = Proposta.objects.create(
            titulo='Proposta de cotas',
            edital=self.edital,
            projeto=self.projeto,
            cotas=2,
            submetido_por=self.pessoa_docente,
            status='aprovada',
        )
        self.aluno_livre = Pessoa.objects.create(
            nome='Aluno Livre', email='livre@alu.test', tipo='aluno',
        )
        self.aluno_com_bolsa = Pessoa.objects.create(
            nome='Aluno Com Bolsa', email='combolsa@alu.test', tipo='aluno',
        )
        Bolsa.objects.create(
            projeto=self.projeto,
            aluno=self.aluno_com_bolsa,
            modalidade=self.modalidade,
            data_inicio=hoje - timedelta(days=10),
            data_fim=hoje + timedelta(days=200),
        )
        self.url_indicar = reverse(
            'proposta_indicar', kwargs={'pk': self.proposta.pk},
        )

    def _indicar(self, aluno):
        """Cria uma indicação pendente direto no ORM."""
        return Indicacao.objects.create(
            proposta=self.proposta,
            aluno=aluno,
            indicado_por=self.pessoa_docente,
        )


class IndicacaoTests(BaseCotasTests):
    """Indicação de aluno para cota de proposta aprovada."""

    def test_docente_submetente_indica_aluno(self):
        self.client.login(username='doc_cotas', password='x')
        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_livre.pk)},
        )
        self.assertEqual(response.status_code, 302)
        indicacao = Indicacao.objects.get(proposta=self.proposta)
        self.assertEqual(indicacao.aluno, self.aluno_livre)
        self.assertEqual(indicacao.indicado_por, self.pessoa_docente)
        self.assertEqual(indicacao.status, 'pendente')
        self.assertIsNone(indicacao.bolsa)

    def test_indicacao_bloqueada_sem_aprovacao_das_cotas(self):
        """Só após aprovação no edital é que se indica (§3.5)."""
        self.proposta.status = 'submetida'
        self.proposta.save()
        self.client.login(username='doc_cotas', password='x')
        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_livre.pk)}, follow=True,
        )
        self.assertContains(response, 'após a aprovação das cotas')
        self.assertFalse(Indicacao.objects.exists())

    def test_indicacao_respeita_limite_de_cotas(self):
        """Cotas=2: duas indicações passam, a terceira é bloqueada."""
        terceiro = Pessoa.objects.create(
            nome='Terceiro Aluno', email='terceiro@alu.test', tipo='aluno',
        )
        self.client.login(username='doc_cotas', password='x')
        for aluno in (self.aluno_livre, terceiro):
            response = self.client.post(
                self.url_indicar, {'aluno': str(aluno.pk)},
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Indicacao.objects.count(), 2)

        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_com_bolsa.pk)},
            follow=True,
        )
        self.assertContains(response, 'já foram indicadas')
        self.assertEqual(Indicacao.objects.count(), 2)

    def test_indicacao_bloqueia_aluno_com_bolsa_ativa(self):
        self.client.login(username='doc_cotas', password='x')
        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_com_bolsa.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui bolsa ativa')
        self.assertFalse(Indicacao.objects.exists())

    def test_aluno_ja_indicado_some_da_lista(self):
        """Aluno já indicado na proposta não volta a aparecer no select."""
        self._indicar(self.aluno_livre)
        self.client.login(username='doc_cotas', password='x')
        response = self.client.get(self.url_indicar)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Aluno Livre')

    def test_tecnico_pode_indicar(self):
        """Téc+ também indica (gerência o fluxo)."""
        self.client.login(username='tec_cotas', password='x')
        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_livre.pk)},
        )
        self.assertEqual(response.status_code, 302)
        indicacao = Indicacao.objects.get(proposta=self.proposta)
        self.assertEqual(indicacao.aluno, self.aluno_livre)
        tec = User.objects.get(username='tec_cotas')
        self.assertEqual(indicacao.indicado_por, tec.perfil.pessoa)

    def test_tecnico_sem_pessoa_indica_sem_erro(self):
        """Téc+ sem Pessoa vinculada: indicação salva com indicado_por nulo."""
        _criar_usuario('tec_sem_pessoa', Perfil.PERFIL_TECNICO, com_pessoa=False)
        self.client.login(username='tec_sem_pessoa', password='x')
        response = self.client.post(
            self.url_indicar, {'aluno': str(self.aluno_livre.pk)},
        )
        self.assertEqual(response.status_code, 302)
        indicacao = Indicacao.objects.get(proposta=self.proposta)
        self.assertIsNone(indicacao.indicado_por)

    def test_docente_nao_submetente_e_403(self):
        self.client.login(username='doc_fora_cotas', password='x')
        response = self.client.get(self.url_indicar)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Indicacao.objects.exists())

    def test_aluno_nao_indica(self):
        self.client.login(username='alu_cotas', password='x')
        self.assertEqual(self.client.get(self.url_indicar).status_code, 403)

    def test_detalhe_mostra_cotas_e_botoes(self):
        """Seção de cotas: indicar (aprovada + disponível) e implementar (só téc+)."""
        self.client.login(username='doc_cotas', password='x')
        detalhe = reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        response = self.client.get(detalhe)
        self.assertContains(response, 'Cotas de bolsa')
        self.assertContains(response, 'Cotas disponíveis')
        self.assertContains(response, '+ Indicar aluno')
        self.assertNotContains(response, 'Implementar bolsa')

        # 1 de 2 cotas indicadas → ainda há disponibilidade
        self._indicar(self.aluno_livre)
        response = self.client.get(detalhe)
        self.assertContains(response, '+ Indicar aluno')
        self.assertContains(response, 'Aluno Livre')
        self.assertNotContains(response, 'Implementar bolsa')

        # todas as cotas indicadas → o botão de indicar some
        extra = Pessoa.objects.create(
            nome='Aluno Extra', email='extra@alu.test', tipo='aluno',
        )
        self._indicar(extra)
        response = self.client.get(detalhe)
        self.assertNotContains(response, '+ Indicar aluno')

        # técnico vê o botão de implementar da indicação pendente
        self.client.logout()
        self.client.login(username='tec_cotas', password='x')
        response = self.client.get(detalhe)
        self.assertContains(response, 'Implementar bolsa')


class ImplementacaoTests(BaseCotasTests):
    """Implementação da bolsa pelo técnico a partir da indicação."""

    def _url_implementar(self, indicacao):
        return reverse('indicacao_implementar', kwargs={'pk': indicacao.pk})

    def test_tecnico_implementa_bolsa(self):
        indicacao = self._indicar(self.aluno_livre)
        url = self._url_implementar(indicacao)

        # Formulário pré-preenchido com aluno, projeto e modalidade
        self.client.login(username='tec_cotas', password='x')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aluno Livre')
        self.assertContains(response, 'PROJ-COTAS-01')

        response = self.client.post(url, {
            'aluno': str(self.aluno_livre.pk),
            'projeto': str(self.projeto.pk),
            'modalidade': str(self.modalidade.pk),
            'data_inicio': str(self.hoje),
            'data_fim': str(self.hoje + timedelta(days=90)),
            'status': 'ativa',
        })
        self.assertEqual(response.status_code, 302)
        bolsa = Bolsa.objects.get(aluno=self.aluno_livre)
        self.assertEqual(bolsa.projeto, self.projeto)
        self.assertEqual(bolsa.modalidade, self.modalidade)
        indicacao.refresh_from_db()
        self.assertEqual(indicacao.status, 'implementada')
        self.assertEqual(indicacao.bolsa, bolsa)

    def test_docente_nao_implementa(self):
        """Implementar é do técnico: docente (mesmo submetente) → 403."""
        indicacao = self._indicar(self.aluno_livre)
        self.client.login(username='doc_cotas', password='x')
        url = self._url_implementar(indicacao)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {}).status_code, 403)
        indicacao.refresh_from_db()
        self.assertEqual(indicacao.status, 'pendente')

    def test_implementacao_duplicada_e_bloqueada(self):
        indicacao = self._indicar(self.aluno_livre)
        indicacao.status = 'implementada'
        indicacao.save()
        self.client.login(username='tec_cotas', password='x')
        response = self.client.get(
            self._url_implementar(indicacao), follow=True,
        )
        self.assertContains(response, 'já foi implementada')
        self.assertEqual(Bolsa.objects.filter(aluno=self.aluno_livre).count(), 0)

    def test_bloqueio_se_aluno_ganhou_bolsa_apos_indicacao(self):
        """Entre indicação e implementação, bolsa ativa impede a criação."""
        indicacao = self._indicar(self.aluno_livre)
        Bolsa.objects.create(
            projeto=self.projeto,
            aluno=self.aluno_livre,
            modalidade=self.modalidade,
            data_inicio=self.hoje,
            data_fim=self.hoje + timedelta(days=90),
        )
        self.client.login(username='tec_cotas', password='x')
        response = self.client.post(self._url_implementar(indicacao), {
            'aluno': str(self.aluno_livre.pk),
            'projeto': str(self.projeto.pk),
            'modalidade': str(self.modalidade.pk),
            'data_inicio': str(self.hoje),
            'data_fim': str(self.hoje + timedelta(days=90)),
            'status': 'ativa',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui bolsa ativa')
        self.assertEqual(Bolsa.objects.filter(aluno=self.aluno_livre).count(), 1)
        indicacao.refresh_from_db()
        self.assertEqual(indicacao.status, 'pendente')


class FilaIndicacoesTests(BaseCotasTests):
    """Fila de indicações: téc+ todas, docente só as suas."""

    def setUp(self):
        super().setUp()
        self.indicacao_propria = self._indicar(self.aluno_livre)
        self.docente_de_fora = User.objects.get(username='doc_fora_cotas')
        self.proposta_alheia = Proposta.objects.create(
            titulo='Proposta alheia',
            edital=self.edital,
            projeto=self.projeto,
            cotas=1,
            submetido_por=self.docente_de_fora.perfil.pessoa,
            status='aprovada',
        )
        aluno_outro = Pessoa.objects.create(
            nome='Aluno da Alheia', email='daalheia@alu.test', tipo='aluno',
        )
        self.indicacao_alheia = Indicacao.objects.create(
            proposta=self.proposta_alheia,
            aluno=aluno_outro,
            indicado_por=self.docente_de_fora.perfil.pessoa,
        )
        self.url = reverse('indicacoes_lista')

    def test_tecnico_ve_todas(self):
        self.client.login(username='tec_cotas', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aluno Livre')
        self.assertContains(response, 'Aluno da Alheia')

    def test_docente_ve_somente_as_de_suas_propostas(self):
        self.client.login(username='doc_cotas', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aluno Livre')
        self.assertNotContains(response, 'Aluno da Alheia')

    def test_docente_sem_propostas_ve_fila_vazia(self):
        """Docente que não submeteu nenhuma proposta não vê indicações."""
        _criar_usuario('doc_vazio', Perfil.PERFIL_DOCENTE)
        self.client.login(username='doc_vazio', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Aluno Livre')
        self.assertNotContains(response, 'Aluno da Alheia')
        self.assertContains(response, 'Nenhuma indicação')

    def test_aluno_nao_acessa_fila(self):
        self.client.login(username='alu_cotas', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)
