"""Testes do módulo de Planos de Trabalho (views, permissões e regras)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.relatorios.models import PlanoTrabalho


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _dados_plano(bolsa, **extras):
    dados = {
        'bolsa': bolsa.pk,
        'titulo': 'Plano de trabalho do aluno',
        'descricao': 'Descrição do plano',
        'objetivos': 'Objetivos do plano',
        'metodologia': 'Metodologia',
        'cronograma': '{"Semana 1": "Revisão bibliográfica"}',
    }
    dados.update(extras)
    return dados


class PlanoAcessoTests(TestCase):
    """Testes de acesso às views de planos de trabalho."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Plano', email='planodoc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.docente_alheio = Pessoa.objects.create(
            nome='Docente Outro', email='outrodoc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno Plano', email='planoalu@alunos.edu.br', tipo='aluno',
            matricula='20260011', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno de Outro', email='outroalu@alunos.edu.br', tipo='aluno',
            matricula='20260012', instituicao=inst,
        )
        self.projeto_meu = Projeto.objects.create(
            codigo='PVDIP-2026', titulo='Projeto com plano',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.projeto_alheio = Projeto.objects.create(
            codigo='PVDIO-2026', titulo='Projeto alheio',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente_alheio, instituicao=inst,
        )
        self.bolsa_com_plano = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.bolsa_sem_plano = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2025, 3, 1), data_fim=date(2025, 11, 30),
            status='encerrada',
        )
        self.bolsa_alheia = Bolsa.objects.create(
            projeto=self.projeto_alheio, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.plano = PlanoTrabalho.objects.create(
            bolsa=self.bolsa_com_plano, aluno=self.aluno1, projeto=self.projeto_meu,
            titulo='Meu plano de pesquisa',
        )
        self.plano_alheio = PlanoTrabalho.objects.create(
            bolsa=self.bolsa_alheia, aluno=self.aluno2, projeto=self.projeto_alheio,
            titulo='Plano do outro aluno', status='submetido',
        )
        _criar_usuario('alu_plano', Perfil.PERFIL_ALUNO, self.aluno1)
        _criar_usuario('doc_plano', Perfil.PERFIL_DOCENTE, self.docente)
        _criar_usuario('doc_outro', Perfil.PERFIL_DOCENTE, self.docente_alheio)
        _criar_usuario('tec_plano', Perfil.PERFIL_TECNICO)

    def test_lista_exige_login(self):
        self.assertEqual(self.client.get(reverse('planos_lista')).status_code, 302)

    def test_aluno_lista_apenas_os_proprios(self):
        self.client.login(username='alu_plano', password='x')
        response = self.client.get(reverse('planos_lista'))
        self.assertContains(response, 'Meu plano de pesquisa')
        self.assertNotContains(response, 'Plano do outro aluno')
        # Tem bolsa sem plano → pode criar
        self.assertContains(response, '+ Novo plano')

    def test_aluno_detalhe_alheio_e_403(self):
        self.client.login(username='alu_plano', password='x')
        response = self.client.get(
            reverse('plano_detalhe', kwargs={'pk': self.plano_alheio.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_aluno_detalhe_mostra_bolsa_e_projeto(self):
        """O detalhe exibe a associação dupla: bolsa e projeto do docente."""
        self.client.login(username='alu_plano', password='x')
        response = self.client.get(
            reverse('plano_detalhe', kwargs={'pk': self.plano.pk})
        )
        self.assertContains(response, reverse('bolsa_detalhe', kwargs={'pk': self.bolsa_com_plano.pk}))
        self.assertContains(response, reverse('projeto_detalhe', kwargs={'pk': self.projeto_meu.pk}))

    def test_aluno_cria_plano_com_vinculos_derivados_da_bolsa(self):
        """Aluno cria plano na própria bolsa; aluno e projeto derivam da bolsa."""
        self.client.login(username='alu_plano', password='x')
        response = self.client.post(
            reverse('plano_novo'), _dados_plano(self.bolsa_sem_plano),
        )
        self.assertEqual(response.status_code, 302)
        plano = PlanoTrabalho.objects.get(bolsa=self.bolsa_sem_plano)
        self.assertEqual(plano.aluno, self.aluno1)
        self.assertEqual(plano.projeto, self.projeto_meu)  # projeto do docente
        self.assertEqual(plano.status, 'rascunho')

    def test_aluno_nao_cria_plano_para_bolsa_de_outro(self):
        self.client.login(username='alu_plano', password='x')
        response = self.client.post(
            reverse('plano_novo'), _dados_plano(self.bolsa_alheia),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'escolha válida')
        # Bolsa alheia continua com apenas o plano do setUp
        self.assertEqual(
            PlanoTrabalho.objects.filter(bolsa=self.bolsa_alheia).count(), 1,
        )

    def test_aluno_edita_apenas_rascunho_ou_reprovado(self):
        self.client.login(username='alu_plano', password='x')
        url = reverse('plano_editar', kwargs={'pk': self.plano.pk})
        self.assertEqual(self.client.get(url).status_code, 200)  # rascunho
        self.plano.status = 'submetido'
        self.plano.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.plano.status = 'aprovado'
        self.plano.save()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_aluno_nao_altera_status(self):
        """Campo status desabilitado: POST tentando aprovar é ignorado."""
        self.client.login(username='alu_plano', password='x')
        response = self.client.post(
            reverse('plano_editar', kwargs={'pk': self.plano.pk}),
            _dados_plano(self.bolsa_com_plano, titulo='Título alterado', status='aprovado'),
        )
        self.assertEqual(response.status_code, 302)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.titulo, 'Título alterado')
        self.assertEqual(self.plano.status, 'rascunho')

    def test_docente_edita_plano_do_seu_projeto(self):
        self.client.login(username='doc_plano', password='x')
        response = self.client.get(
            reverse('plano_editar', kwargs={'pk': self.plano.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_docente_alheio_nao_edita(self):
        self.client.login(username='doc_outro', password='x')
        response = self.client.get(
            reverse('plano_editar', kwargs={'pk': self.plano.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_docente_nao_cria_plano_para_projeto_alheio(self):
        self.client.login(username='doc_plano', password='x')
        response = self.client.post(
            reverse('plano_novo'), _dados_plano(self.bolsa_alheia),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'escolha válida')

    def test_tecnico_aprova_plano_com_carimbo(self):
        """Técnico aprova via edição; data_aprovacao é carimbada."""
        self.client.login(username='tec_plano', password='x')
        response = self.client.post(
            reverse('plano_editar', kwargs={'pk': self.plano.pk}),
            _dados_plano(self.bolsa_com_plano, status='aprovado'),
        )
        self.assertEqual(response.status_code, 302)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, 'aprovado')
        self.assertIsNotNone(self.plano.data_submissao)
        self.assertIsNotNone(self.plano.data_aprovacao)

    def test_um_plano_por_bolsa(self):
        """Mover um plano para bolsa que já tem plano é rejeitado.

        Na criação o queryset já exclui bolsas com plano; na edição a
        validação de clean() derruba a tentativa com mensagem clara.
        """
        self.client.login(username='tec_plano', password='x')
        response = self.client.post(
            reverse('plano_editar', kwargs={'pk': self.plano_alheio.pk}),
            _dados_plano(self.bolsa_com_plano),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui plano de trabalho')
        self.plano_alheio.refresh_from_db()
        self.assertEqual(self.plano_alheio.bolsa, self.bolsa_alheia)


class IntegracoesTests(TestCase):
    """Integrações: página da bolsa e painel do aluno."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        docente = Pessoa.objects.create(
            nome='Docente Int', email='int@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        aluno = Pessoa.objects.create(
            nome='Aluno Int', email='int@alunos.edu.br', tipo='aluno',
            matricula='20260021', instituicao=inst,
        )
        projeto = Projeto.objects.create(
            codigo='PVDII-2026', titulo='Projeto integração',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=docente, instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=projeto, aluno=aluno, modalidade=modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.plano = PlanoTrabalho.objects.create(
            bolsa=self.bolsa, aluno=aluno, projeto=projeto,
            titulo='Plano integrado',
        )
        _criar_usuario('alu_int', Perfil.PERFIL_ALUNO, aluno)
        _criar_usuario('doc_int', Perfil.PERFIL_DOCENTE, docente)
        # Docente NÃO coordenador (qualquer docente vê os planos)
        docente_visitante = Pessoa.objects.create(
            nome='Docente Visitante', email='visit@unifei.edu.br', tipo='docente',
        )
        _criar_usuario('doc_vis', Perfil.PERFIL_DOCENTE, docente_visitante)

    def test_bolsa_detalhe_mostra_plano(self):
        """A página da bolsa exibe o plano de trabalho vinculado."""
        self.client.login(username='doc_int', password='x')
        response = self.client.get(reverse('bolsa_detalhe', kwargs={'pk': self.bolsa.pk}))
        self.assertContains(response, 'Plano integrado')
        self.assertContains(response, reverse('plano_detalhe', kwargs={'pk': self.plano.pk}))

    def test_painel_aluno_lista_seus_planos(self):
        self.client.login(username='alu_int', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Seus planos de trabalho')
        self.assertContains(response, 'Plano integrado')
        self.assertContains(response, reverse('plano_detalhe', kwargs={'pk': self.plano.pk}))

    def test_projeto_linka_planos_das_bolsas_para_docente(self):
        """Docente+ vê a coluna Plano de trabalho nas bolsas do projeto."""
        self.client.login(username='doc_int', password='x')
        response = self.client.get(
            reverse('projeto_detalhe', kwargs={'pk': self.bolsa.projeto.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>Plano de trabalho</th>')
        self.assertContains(response, reverse('plano_detalhe', kwargs={'pk': self.plano.pk}))

    def test_docente_nao_coordenador_tambem_ve_links_dos_planos(self):
        """Docente não coordenador vê os planos ao visualizar o projeto."""
        self.client.login(username='doc_vis', password='x')
        response = self.client.get(
            reverse('projeto_detalhe', kwargs={'pk': self.bolsa.projeto.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>Plano de trabalho</th>')
        self.assertContains(response, reverse('plano_detalhe', kwargs={'pk': self.plano.pk}))

    def test_aluno_ve_projeto_mas_sem_links_de_plano(self):
        """Aluno vê o projeto (tem bolsa) mas sem links dos planos de terceiros."""
        self.client.login(username='alu_int', password='x')
        response = self.client.get(
            reverse('projeto_detalhe', kwargs={'pk': self.bolsa.projeto.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<th>Plano de trabalho</th>')
        self.assertNotContains(response, reverse('plano_detalhe', kwargs={'pk': self.plano.pk}))
