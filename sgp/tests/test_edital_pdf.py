"""Testes do PDF do edital (documento oficial anexado pelo técnico).

Regras verificadas (§3.1):
- criar/editar edital continua livre (rascunho pode nascer sem documento);
- upload validado no servidor (extensão, tamanho e assinatura `%PDF-`);
- "Aprovar e validar" exige o PDF anexado — a redação oficial do edital
  (objeto, cronograma, requisitos) vive no documento que o validador lê;
- o PDF só é servido por rota autenticada com a permissão do detalhe
  (abaixo de técnicos, apenas o edital em execução);
- a lista busca por código, título e descrição.
"""
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil
from apps.bolsas.models import ModalidadeBolsa
from apps.editais.models import Edital

from sgp.tests.arquivos_teste import MediaTemporariaMixin, PDF_EXEMPLO, anexar_pdf

from .test_editais import _criar_edital, _criar_usuario


def _pdf(nome='edital.pdf', conteudo=None):
    """Arquivo enviado simulado (o conteúdo vai dentro do POST)."""
    return SimpleUploadedFile(nome, conteudo or PDF_EXEMPLO)


def _dados_edital(**extras):
    """Ficha mínima do edital para o formulário."""
    return {
        'codigo': 'EDITAL-PDF-01',
        'titulo': 'Edital com documento em PDF',
        'descricao': 'Edital para seleção de propostas com cronograma.',
        'data_inicio': '2026-03-01',
        'data_fim': '2026-06-30',
        'nota_minima': '6.00',
        **extras,
    }


class FormularioEditalPdfTests(MediaTemporariaMixin, TestCase):
    """Formulário do edital: campo de PDF, upload validado e substituição."""

    def setUp(self):
        super().setUp()
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        _criar_usuario('tec_edt_pdf', Perfil.PERFIL_TECNICO)
        self.client.login(username='tec_edt_pdf', password='x')

    def test_formulario_declara_multipart_e_campo_de_arquivo(self):
        """Sem enctype o upload é ignorado silenciosamente."""
        response = self.client.get(reverse('edital_novo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="arquivo_pdf"')

    def test_cria_edital_com_pdf(self):
        payload = _dados_edital(modalidade=self.modalidade.pk)
        payload['arquivo_pdf'] = _pdf()
        response = self.client.post(reverse('edital_novo'), payload)
        self.assertEqual(response.status_code, 302)
        edital = Edital.objects.get(codigo='EDITAL-PDF-01')
        self.assertTrue(edital.arquivo_pdf.name.startswith('uploads/editais/'))
        self.assertEqual(edital.status, 'rascunho')

    def test_rascunho_pode_nascer_sem_pdf(self):
        """Obrigatório só na aprovação: criar sem documento é permitido."""
        response = self.client.post(
            reverse('edital_novo'), _dados_edital(modalidade=self.modalidade.pk)
        )
        self.assertEqual(response.status_code, 302)
        edital = Edital.objects.get(codigo='EDITAL-PDF-01')
        self.assertFalse(edital.arquivo_pdf)

    def test_arquivo_que_nao_e_pdf_e_recusado_no_servidor(self):
        payload = _dados_edital(modalidade=self.modalidade.pk)
        payload['arquivo_pdf'] = _pdf('edital.txt', conteudo=b'nao e um pdf')
        response = self.client.post(reverse('edital_novo'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Anexe o documento em formato PDF (.pdf).')
        self.assertFalse(Edital.objects.filter(codigo='EDITAL-PDF-01').exists())

    def test_substituir_pdf_apaga_o_anterior_do_disco(self):
        edital = _criar_edital(modalidade=self.modalidade)
        anexar_pdf(edital, nome='antigo.pdf')
        caminho_antigo = edital.arquivo_pdf.path

        edital.arquivo_pdf = _pdf('novo.pdf')
        edital.save()

        self.assertFalse(Path(caminho_antigo).exists())


class AprovacaoExigePdfTests(MediaTemporariaMixin, TestCase):
    """Aprovação do edital: o validador precisa ler o documento."""

    def setUp(self):
        super().setUp()
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.edital = _criar_edital('rascunho', modalidade=self.modalidade)
        _criar_usuario('dir_edt_pdf', Perfil.PERFIL_DIRETOR)
        _criar_usuario('tec_edt_pdf', Perfil.PERFIL_TECNICO)

    def _acao(self, nome):
        return self.client.post(
            reverse('edital_acao', kwargs={'pk': self.edital.pk, 'acao': nome}),
            follow=True,
        )

    def test_aprovar_sem_pdf_e_bloqueado(self):
        self.client.login(username='dir_edt_pdf', password='x')
        response = self._acao('aprovar')

        self.assertContains(response, 'Anexe o PDF do edital')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'rascunho')
        self.assertIsNone(self.edital.validado_por)
        self.assertIsNone(self.edital.data_validacao)

    def test_aprovar_com_pdf_valida(self):
        anexar_pdf(self.edital)
        self.client.login(username='dir_edt_pdf', password='x')
        response = self._acao('aprovar')

        self.assertContains(response, 'aprovado e validado')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'aprovado')
        self.assertEqual(self.edital.validado_por.username, 'dir_edt_pdf')

    def test_cancelar_nao_exige_pdf(self):
        """Só a aprovação exige documento — cancelar um rascunho, não."""
        self.client.login(username='tec_edt_pdf', password='x')
        self._acao('cancelar')
        self.edital.refresh_from_db()
        self.assertEqual(self.edital.status, 'cancelado')


class ArquivoEditalTests(MediaTemporariaMixin, TestCase):
    """Rota do PDF: mesma permissão do detalhe, nunca /media/ público."""

    def setUp(self):
        super().setUp()
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        _criar_usuario('alu_edt_pdf', Perfil.PERFIL_ALUNO)
        _criar_usuario('tec_edt_pdf', Perfil.PERFIL_TECNICO)

    def _url(self, edital):
        return reverse('edital_arquivo', kwargs={'pk': edital.pk})

    def test_nao_logado_e_redirecionado_para_login(self):
        edital = _criar_edital('em_andamento', modalidade=self.modalidade)
        anexar_pdf(edital)
        self.assertEqual(self.client.get(self._url(edital)).status_code, 302)

    def test_tecnico_baixa_pdf_de_edital_em_rascunho(self):
        edital = _criar_edital('rascunho', modalidade=self.modalidade)
        anexar_pdf(edital)
        self.client.login(username='tec_edt_pdf', password='x')
        response = self.client.get(self._url(edital))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_aluno_nao_acessa_pdf_de_edital_fora_de_execucao(self):
        edital = _criar_edital('rascunho', modalidade=self.modalidade)
        anexar_pdf(edital)
        self.client.login(username='alu_edt_pdf', password='x')
        self.assertEqual(self.client.get(self._url(edital)).status_code, 403)

    def test_aluno_baixa_pdf_do_edital_em_execucao(self):
        edital = _criar_edital('em_andamento', modalidade=self.modalidade)
        anexar_pdf(edital)
        self.client.login(username='alu_edt_pdf', password='x')
        response = self.client.get(self._url(edital))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_edital_sem_documento_retorna_404(self):
        edital = _criar_edital('em_andamento', modalidade=self.modalidade)
        self.client.login(username='alu_edt_pdf', password='x')
        self.assertEqual(self.client.get(self._url(edital)).status_code, 404)


class BuscaEditalTests(TestCase):
    """A busca da lista cobre código, título e descrição (padrão das listas)."""

    def setUp(self):
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.edital = _criar_edital(
            'em_andamento',
            modalidade=self.modalidade,
            codigo='PIBIC-2026-08',
            titulo='Bolsas PIBIC FAPEMIG 2027-2028',
            descricao='Cronograma de inscrição e requisitos de habilitação.',
        )
        _criar_usuario('tec_busca', Perfil.PERFIL_TECNICO)
        self.client.login(username='tec_busca', password='x')

    def _buscar(self, termo):
        response = self.client.get(reverse('editais_lista'), {'q': termo})
        return response.context['editais']

    def test_busca_por_codigo(self):
        self.assertIn(self.edital, self._buscar('2026-08'))

    def test_busca_por_titulo(self):
        self.assertIn(self.edital, self._buscar('FAPEMIG'))

    def test_busca_por_descricao(self):
        """A redação curta é o texto pesquisável (o resto fica no PDF)."""
        self.assertIn(self.edital, self._buscar('habilitação'))

    def test_termo_inexistente_nao_retorna_nada(self):
        self.assertEqual(list(self._buscar('zzzzqwer')), [])
