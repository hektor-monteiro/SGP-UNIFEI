"""Testes do PDF e do resumo do Relatório (submissão em PDF).

Regras verificadas:
- `resumo` obrigatório (alimenta a busca do sistema);
- "Submeter para avaliação" exige o PDF anexado;
- o PDF só é servido por rota autenticada com a permissão do detalhe
  (aluno só vê os próprios relatórios);
- a avaliação exibe o link do documento que o avaliador vai ler;
- a lista busca por título e resumo.
"""
from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.core.models import Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto
from apps.relatorios.models import Relatorio
from sgp.tests.arquivos_teste import PDF_EXEMPLO, MediaTemporariaMixin, anexar_pdf

from .test_relatorios import _criar_usuario, _dados_relatorio


def _pdf(conteudo=None):
    return SimpleUploadedFile('relatorio.pdf', conteudo or PDF_EXEMPLO)


class BaseRelatorioPdfTests(MediaTemporariaMixin, TestCase):
    """Fixtures comuns: bolsa com relatório em rascunho."""

    def setUp(self):
        super().setUp()
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Rel PDF', email='docrelpdf@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Rel PDF', email='alurelpdf@alunos.edu.br',
            tipo='aluno', matricula='20263333', instituicao=inst,
        )
        self.aluno_fora = Pessoa.objects.create(
            nome='Aluno Rel Fora', email='relfora@alunos.edu.br',
            tipo='aluno', matricula='20264444', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PVDI897-2026',
            titulo='Projeto do relatório com PDF',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=self.docente,
            instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.rel = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno, tipo='parcial',
            titulo='Relatório parcial com PDF',
            resumo='Resumo do relatório para a busca do sistema.',
            periodo_inicio=date(2026, 3, 1), periodo_fim=date(2026, 8, 31),
        )
        self.url_editar = reverse('relatorio_editar', kwargs={'pk': self.rel.pk})
        self.url_submeter = reverse(
            'relatorio_submeter', kwargs={'pk': self.rel.pk},
        )
        self.url_arquivo = reverse('relatorio_arquivo', kwargs={'pk': self.rel.pk})

        _criar_usuario('alu_relpdf', Perfil.PERFIL_ALUNO, self.aluno)
        _criar_usuario('alu_relfora', Perfil.PERFIL_ALUNO, self.aluno_fora)
        _criar_usuario('doc_relpdf', Perfil.PERFIL_DOCENTE, self.docente)
        _criar_usuario('tec_relpdf', Perfil.PERFIL_TECNICO)


class SubmissaoRelatorioPdfTests(BaseRelatorioPdfTests):
    """Submissão do relatório em PDF."""

    def test_criar_sem_pdf_e_permitido(self):
        """O PDF só é obrigatório na submissão — criar fica livre."""
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(
            reverse('relatorio_novo'), _dados_relatorio(self.bolsa),
        )
        self.assertEqual(response.status_code, 302)
        relatorio = Relatorio.objects.get(titulo='Relatório parcial de pesquisa')
        self.assertEqual(relatorio.status, 'rascunho')
        self.assertFalse(relatorio.arquivo_pdf)

    def test_submeter_sem_pdf_e_bloqueado(self):
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(self.url_submeter, follow=True)
        self.assertContains(response, 'Anexe o PDF do relatório')
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.status, 'rascunho')

    def test_submeter_com_pdf_envia(self):
        anexar_pdf(self.rel, nome='relatorio.pdf')
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(self.url_submeter, follow=True)
        self.assertContains(response, 'Relatório submetido para avaliação')
        self.rel.refresh_from_db()
        self.assertEqual(self.rel.status, 'submetido')

    def test_resumo_obrigatorio(self):
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(
            self.url_editar, _dados_relatorio(self.bolsa, resumo=''),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('resumo', response.context['form'].errors)

    def test_pdf_invalido_e_rejeitado(self):
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(
            self.url_editar,
            _dados_relatorio(self.bolsa, arquivo_pdf=_pdf(conteudo=b'nao pdf')),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('arquivo_pdf', response.context['form'].errors)

    def test_upload_de_pdf_no_relatorio(self):
        """O arquivo vai para MEDIA_ROOT e aparece no detalhe."""
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.post(
            self.url_editar,
            _dados_relatorio(self.bolsa, arquivo_pdf=_pdf()),
        )
        self.assertEqual(response.status_code, 302)
        self.rel.refresh_from_db()
        self.assertTrue(
            self.rel.arquivo_pdf.name.startswith('uploads/relatorios/'),
        )
        detalhe = self.client.get(
            reverse('relatorio_detalhe', kwargs={'pk': self.rel.pk}),
        )
        self.assertContains(detalhe, 'Abrir o PDF do relatório')
        self.assertContains(detalhe, self.url_arquivo)


class ArquivoRelatorioTests(BaseRelatorioPdfTests):
    """A rota do PDF aplica a mesma visibilidade do detalhe."""

    def setUp(self):
        super().setUp()
        anexar_pdf(self.rel, nome='relatorio-anexo.pdf')
        self.rel.status = 'submetido'
        self.rel.save()

    def test_exige_login(self):
        response = self.client.get(self.url_arquivo)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/contas/entrar/', response.url)

    def test_aluno_proprio_baixa_o_pdf(self):
        self.client.login(username='alu_relpdf', password='x')
        response = self.client.get(self.url_arquivo)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('relatorio-anexo.pdf', response['Content-Disposition'])

    def test_aluno_de_outro_relatorio_nao_baixa(self):
        self.client.login(username='alu_relfora', password='x')
        self.assertEqual(self.client.get(self.url_arquivo).status_code, 403)

    def test_orientador_baixa_o_pdf(self):
        self.client.login(username='doc_relpdf', password='x')
        self.assertEqual(self.client.get(self.url_arquivo).status_code, 200)

    def test_relatorio_sem_arquivo_retorna_404(self):
        sem_pdf = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno, tipo='final',
            titulo='Relatório final sem documento',
            resumo='Resumo sem PDF anexado.',
        )
        self.client.login(username='tec_relpdf', password='x')
        url = reverse('relatorio_arquivo', kwargs={'pk': sem_pdf.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_avaliacao_exibe_link_do_pdf(self):
        """O avaliador precisa alcançar o documento na tela de avaliação."""
        self.client.login(username='tec_relpdf', password='x')
        response = self.client.get(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Documento do relatório')
        self.assertContains(response, 'Abrir o PDF')


class BuscaRelatorioPorResumoTests(TestCase):
    """A lista de relatórios busca por título e resumo."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        docente = Pessoa.objects.create(
            nome='Docente Busca Rel', email='docbuscarel@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        aluno1 = Pessoa.objects.create(
            nome='Aluno Rel Biossensores', email='relbios@alunos.edu.br',
            tipo='aluno', matricula='20261212', instituicao=inst,
        )
        aluno2 = Pessoa.objects.create(
            nome='Aluno Rel Geometria', email='relgeo@alunos.edu.br',
            tipo='aluno', matricula='20261313', instituicao=inst,
        )
        projeto = Projeto.objects.create(
            codigo='PVDI898-2026',
            titulo='Projeto da busca de relatórios',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=docente,
            instituicao=inst,
        )
        self.alvo = Relatorio.objects.create(
            bolsa=Bolsa.objects.create(
                projeto=projeto, aluno=aluno1, modalidade=modalidade,
                data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
            ),
            aluno=aluno1, tipo='parcial',
            titulo='Relatório de biossensores',
            resumo='Apresenta dados de biotecnologia monitorada no rio.',
            nota=Decimal('8.00'),
        )
        self.outro = Relatorio.objects.create(
            bolsa=Bolsa.objects.create(
                projeto=projeto, aluno=aluno2, modalidade=modalidade,
                data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
            ),
            aluno=aluno2, tipo='parcial',
            titulo='Relatório de geometria',
            resumo='Área pura da matemática, sem relação com biotecnologia.',
        )
        _criar_usuario('tec_buscarel', Perfil.PERFIL_TECNICO)
        self.url = reverse('relatorios_lista')
        self.client.login(username='tec_buscarel', password='x')

    def test_busca_por_resumo(self):
        response = self.client.get(self.url, {'q': 'biotecnologia monitorada'})
        self.assertContains(response, 'Relatório de biossensores')
        self.assertNotContains(response, 'Relatório de geometria')

    def test_busca_por_titulo(self):
        response = self.client.get(self.url, {'q': 'geometria'})
        self.assertContains(response, 'Relatório de geometria')
        self.assertNotContains(response, 'Relatório de biossensores')

    def test_placeholder_sugere_resumo(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Título ou resumo')
