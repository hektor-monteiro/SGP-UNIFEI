"""Testes do PDF e do resumo do Plano de Trabalho (submissão em PDF).

Regras verificadas:
- `resumo` obrigatório (alimenta a busca do sistema);
- status diferente de 'Rascunho' exige o PDF anexado (submissão);
- o PDF só é servido por rota autenticada com a permissão do detalhe
  (aluno só vê os próprios planos);
- a lista busca por título e resumo.
"""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.core.models import Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto
from apps.relatorios.models import PlanoTrabalho
from sgp.tests.arquivos_teste import MediaTemporariaMixin, anexar_pdf

from .test_planos import _criar_usuario, _dados_plano, _pdf


class PlanoPdfTests(MediaTemporariaMixin, TestCase):
    """Submissão do plano em PDF + entrega do arquivo com permissão."""

    def setUp(self):
        super().setUp()
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        docente = Pessoa.objects.create(
            nome='Docente Plano PDF', email='docplanopdf@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Plano PDF', email='aluplanopdf@alunos.edu.br',
            tipo='aluno', matricula='20267777', instituicao=inst,
        )
        self.aluno_fora = Pessoa.objects.create(
            nome='Aluno Plano Outro', email='planooutro@alunos.edu.br',
            tipo='aluno', matricula='20266666', instituicao=inst,
        )
        projeto = Projeto.objects.create(
            codigo='PVDI894-2026',
            titulo='Projeto do plano de trabalho',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=docente,
            instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=projeto, aluno=self.aluno, modalidade=modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.plano = PlanoTrabalho.objects.create(
            bolsa=self.bolsa, aluno=self.aluno, projeto=projeto,
            titulo='Plano de trabalho com PDF',
            resumo='Resumo do plano para a busca do sistema.',
        )
        self.url_editar = reverse('plano_editar', kwargs={'pk': self.plano.pk})
        self.url_arquivo = reverse('plano_arquivo', kwargs={'pk': self.plano.pk})

        _criar_usuario('alu_plpdf', Perfil.PERFIL_ALUNO, self.aluno)
        _criar_usuario('alu_plfora', Perfil.PERFIL_ALUNO, self.aluno_fora)
        _criar_usuario('tec_plpdf', Perfil.PERFIL_TECNICO)

    def test_submeter_sem_pdf_e_bloqueado(self):
        """Status 'submetido' sem PDF: mensagem clara e nada muda."""
        self.client.login(username='tec_plpdf', password='x')
        response = self.client.post(
            self.url_editar,
            _dados_plano(self.bolsa, status='submetido'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Anexe o PDF do plano de trabalho')
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, 'rascunho')
        self.assertFalse(self.plano.arquivo_pdf)

    def test_submeter_com_pdf_envia(self):
        self.client.login(username='tec_plpdf', password='x')
        response = self.client.post(
            self.url_editar,
            _dados_plano(self.bolsa, status='submetido', arquivo_pdf=_pdf()),
        )
        self.assertEqual(response.status_code, 302)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, 'submetido')
        self.assertTrue(self.plano.arquivo_pdf.name.startswith('uploads/planos/'))

    def test_rascunho_fica_sem_pdf(self):
        """Criar/editar em rascunho continua livre de PDF."""
        self.client.login(username='tec_plpdf', password='x')
        response = self.client.post(
            self.url_editar,
            _dados_plano(self.bolsa, titulo='Rascunho novo', status='rascunho'),
        )
        self.assertEqual(response.status_code, 302)
        self.plano.refresh_from_db()
        self.assertEqual(self.plano.status, 'rascunho')

    def test_resumo_obrigatorio(self):
        self.client.login(username='tec_plpdf', password='x')
        response = self.client.post(
            self.url_editar, _dados_plano(self.bolsa, resumo=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('resumo', response.context['form'].errors)

    def test_pdf_invalido_e_rejeitado(self):
        self.client.login(username='tec_plpdf', password='x')
        response = self.client.post(
            self.url_editar,
            {
                'bolsa': self.bolsa.pk,
                'titulo': 'Plano com PDF falso',
                'resumo': 'Resumo qualquer para a busca.',
                'status': 'submetido',
                'arquivo_pdf': _pdf(conteudo=b'<html>nao e pdf</html>'),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('arquivo_pdf', response.context['form'].errors)


class ArquivoPlanoTests(MediaTemporariaMixin, TestCase):
    """A rota do PDF do plano aplica a mesma visibilidade do detalhe."""

    def setUp(self):
        super().setUp()
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        docente = Pessoa.objects.create(
            nome='Docente Arquivo Plano', email='docarqplano@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Arquivo Plano', email='aluarqplano@alunos.edu.br',
            tipo='aluno', matricula='20265555', instituicao=inst,
        )
        self.aluno_fora = Pessoa.objects.create(
            nome='Aluno Arquivo Fora', email='arqfora@alunos.edu.br',
            tipo='aluno', matricula='20264444', instituicao=inst,
        )
        projeto = Projeto.objects.create(
            codigo='PVDI895-2026',
            titulo='Projeto do arquivo do plano',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=docente,
            instituicao=inst,
        )
        bolsa = Bolsa.objects.create(
            projeto=projeto, aluno=self.aluno, modalidade=modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.plano = PlanoTrabalho.objects.create(
            bolsa=bolsa, aluno=self.aluno, projeto=projeto,
            titulo='Plano com documento',
            resumo='Resumo do plano com PDF anexado.',
            status='submetido',
        )
        anexar_pdf(self.plano, nome='plano-anexo.pdf')
        self.url = reverse('plano_arquivo', kwargs={'pk': self.plano.pk})

        _criar_usuario('alu_arqpl', Perfil.PERFIL_ALUNO, self.aluno)
        _criar_usuario('alu_arqfora', Perfil.PERFIL_ALUNO, self.aluno_fora)
        _criar_usuario('tec_arqpl', Perfil.PERFIL_TECNICO)

    def test_exige_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/contas/entrar/', response.url)

    def test_aluno_proprio_baixa_o_pdf(self):
        self.client.login(username='alu_arqpl', password='x')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('plano-anexo.pdf', response['Content-Disposition'])

    def test_aluno_de_outro_plano_nao_baixa(self):
        self.client.login(username='alu_arqfora', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_tecnico_baixa_o_pdf(self):
        self.client.login(username='tec_arqpl', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_plano_sem_arquivo_retorna_404(self):
        # Um plano por bolsa: uso a bolsa do outro aluno (sem plano)
        bolsa_fora = Bolsa.objects.create(
            projeto=self.plano.projeto, aluno=self.aluno_fora,
            modalidade=self.plano.bolsa.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        sem_pdf = PlanoTrabalho.objects.create(
            bolsa=bolsa_fora, aluno=self.aluno_fora, projeto=self.plano.projeto,
            titulo='Plano sem documento',
        )
        self.client.login(username='tec_arqpl', password='x')
        url = reverse('plano_arquivo', kwargs={'pk': sem_pdf.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_detalhe_exibe_resumo_e_link_do_pdf(self):
        self.client.login(username='tec_arqpl', password='x')
        response = self.client.get(
            reverse('plano_detalhe', kwargs={'pk': self.plano.pk}),
        )
        self.assertContains(response, 'Resumo do plano com PDF anexado.')
        self.assertContains(response, 'Abrir o PDF do plano de trabalho')
        self.assertContains(response, self.url)


class BuscaPlanoPorResumoTests(TestCase):
    """A lista de planos busca por título e resumo."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        docente = Pessoa.objects.create(
            nome='Docente Busca Plano', email='docbuscaplano@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        aluno1 = Pessoa.objects.create(
            nome='Aluno Biossensores', email='bios@alunos.edu.br',
            tipo='aluno', matricula='20261111', instituicao=inst,
        )
        aluno2 = Pessoa.objects.create(
            nome='Aluno Geometria', email='geo@alunos.edu.br',
            tipo='aluno', matricula='20262222', instituicao=inst,
        )
        projeto = Projeto.objects.create(
            codigo='PVDI896-2026',
            titulo='Projeto da busca de planos',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=docente,
            instituicao=inst,
        )
        self.alvo = PlanoTrabalho.objects.create(
            bolsa=Bolsa.objects.create(
                projeto=projeto, aluno=aluno1, modalidade=modalidade,
                data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
            ),
            aluno=aluno1, projeto=projeto,
            titulo='Plano de biossensores',
            resumo='Trata de biotecnologia aplicada à monitoração de rios.',
        )
        self.outro = PlanoTrabalho.objects.create(
            bolsa=Bolsa.objects.create(
                projeto=projeto, aluno=aluno2, modalidade=modalidade,
                data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
            ),
            aluno=aluno2, projeto=projeto,
            titulo='Plano de geometria',
            resumo='Área pura da matemática, sem relação com biotecnologia.',
        )
        _criar_usuario('tec_buscapl', Perfil.PERFIL_TECNICO)
        self.url = reverse('planos_lista')
        self.client.login(username='tec_buscapl', password='x')

    def test_busca_por_resumo(self):
        response = self.client.get(self.url, {'q': 'biotecnologia aplicada'})
        self.assertContains(response, 'Plano de biossensores')
        self.assertNotContains(response, 'Plano de geometria')

    def test_busca_por_titulo(self):
        response = self.client.get(self.url, {'q': 'geometria'})
        self.assertContains(response, 'Plano de geometria')
        self.assertNotContains(response, 'Plano de biossensores')

    def test_placeholder_sugere_resumo(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Título ou resumo')
