"""Testes do PDF e do resumo do projeto (submissão de projetos em PDF).

Regras verificadas (§3.1):
- `resumo` obrigatório no formulário (alimenta a busca do sistema);
- upload validado no servidor (extensão, tamanho e assinatura `%PDF-`);
- arquivo substituído é apagado do disco (nada de PDF órfão);
- "Enviar para avaliação por pares" exige o PDF anexado;
- o PDF só é servido por rota autenticada com a permissão do detalhe;
- a lista busca por código, título e resumo.
"""
from datetime import date

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil
from apps.equipes.models import MembroEquipe
from apps.projetos.models import (
    GrandeAreaConhecimento,
    ODS,
    Pessoa,
    Projeto,
)
from sgp.tests.arquivos_teste import MediaTemporariaMixin, PDF_EXEMPLO, anexar_pdf

from .test_projetos import _criar_usuario


def _dados_projeto(**extras):
    """Ficha ODS + CNPq obrigatória em cadeia coerente (GA→Área→Subárea)."""
    grande_area = GrandeAreaConhecimento.objects.first()
    area = grande_area.areas.first()
    subarea = area.subareas.first()
    return {
        'codigo': 'PVDI888-2026',
        'titulo': 'Projeto com documento em PDF',
        'resumo': 'Resumo curto do projeto para a busca do sistema.',
        'data_registro': date.today().isoformat(),
        'data_inicio': date.today().isoformat(),
        'status': 'vigente',
        'ods': [ODS.objects.first().pk],
        'grande_area': grande_area.pk,
        'area': area.pk,
        'subarea': subarea.pk,
        **extras,
    }


def _pdf(nome='projeto.pdf', conteudo=None):
    return SimpleUploadedFile(nome, conteudo or PDF_EXEMPLO)


class FormularioProjetoPdfTests(MediaTemporariaMixin, TestCase):
    """Formulário do projeto: resumo obrigatório e upload validado."""

    def setUp(self):
        super().setUp()
        self.docente = Pessoa.objects.create(
            nome='Docente PDF', email='docpdf@unifei.edu.br', tipo='docente',
        )
        self.user = _criar_usuario('tec_pdf', Perfil.PERFIL_TECNICO)
        self.client.login(username='tec_pdf', password='x')

    def _post(self, dados=None, arquivo=None, url=None):
        payload = _dados_projeto(**(dados or {}))
        if arquivo:
            # No client do Django o arquivo vai dentro do próprio dicionário
            payload['arquivo_pdf'] = arquivo
        return self.client.post(url or reverse('projeto_novo'), payload)

    def test_cria_com_resumo_e_pdf(self):
        response = self._post(arquivo=_pdf())
        self.assertEqual(response.status_code, 302)
        projeto = Projeto.objects.get(codigo='PVDI888-2026')
        self.assertTrue(projeto.resumo)
        self.assertTrue(projeto.arquivo_pdf.name.startswith('uploads/projetos/'))
        # o arquivo existe no disco (MEDIA_ROOT temporário do teste)
        self.assertTrue(projeto.arquivo_pdf.storage.exists(projeto.arquivo_pdf.name))

    def test_cria_sem_pdf_e_permitido(self):
        """O PDF só é obrigatório na submissão — criar fica livre."""
        self.assertEqual(self._post().status_code, 302)
        projeto = Projeto.objects.get(codigo='PVDI888-2026')
        self.assertFalse(projeto.arquivo_pdf)

    def test_resumo_obrigatorio(self):
        response = self._post(dados={'resumo': ''})
        self.assertEqual(response.status_code, 200)
        self.assertIn('resumo', response.context['form'].errors)

    def test_resumo_com_limite_de_1000_caracteres(self):
        response = self._post(dados={'resumo': 'x' * 1001})
        self.assertEqual(response.status_code, 200)
        self.assertIn('resumo', response.context['form'].errors)

    def test_pdf_com_assinatura_invalida_e_rejeitado(self):
        """Extensão .pdf mente: o conteúdo precisa começar com %PDF-."""
        response = self._post(
            arquivo=_pdf(conteudo=b'<html>nao e um pdf</html>'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('arquivo_pdf', response.context['form'].errors)
        self.assertFalse(Projeto.objects.filter(codigo='PVDI888-2026').exists())

    def test_extensao_diferente_e_rejeitada(self):
        response = self._post(
            arquivo=_pdf(nome='projeto.docx', conteudo=b'PK\x03\x04'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('arquivo_pdf', response.context['form'].errors)

    def test_edicao_sem_reenvio_mantem_o_pdf(self):
        self._post(arquivo=_pdf())
        projeto = Projeto.objects.get(codigo='PVDI888-2026')
        nome_original = projeto.arquivo_pdf.name

        response = self._post(
            dados={'titulo': 'Título revisado'},
            url=reverse('projeto_editar', kwargs={'pk': projeto.pk}),
        )
        self.assertEqual(response.status_code, 302)
        projeto.refresh_from_db()
        self.assertEqual(projeto.titulo, 'Título revisado')
        self.assertEqual(projeto.arquivo_pdf.name, nome_original)

    def test_substituir_pdf_apaga_o_anterior(self):
        """Higiene de arquivos: nada de PDF órfão em MEDIA_ROOT."""
        import os

        self._post(arquivo=_pdf(nome='original.pdf'))
        projeto = Projeto.objects.get(codigo='PVDI888-2026')
        caminho_antigo = projeto.arquivo_pdf.path

        response = self._post(
            dados={'titulo': 'Com PDF novo'},
            arquivo=_pdf(nome='novo.pdf'),
            url=reverse('projeto_editar', kwargs={'pk': projeto.pk}),
        )
        self.assertEqual(response.status_code, 302)
        projeto.refresh_from_db()
        self.assertTrue(projeto.arquivo_pdf.name.endswith('novo.pdf'))
        self.assertTrue(projeto.arquivo_pdf.storage.exists(projeto.arquivo_pdf.name))
        self.assertFalse(os.path.exists(caminho_antigo))


class SubmissaoProjetoComPdfTests(MediaTemporariaMixin, TestCase):
    """"Enviar para avaliação por pares" exige o PDF anexado."""

    def setUp(self):
        super().setUp()
        pessoa = Pessoa.objects.create(
            nome='Coordenador PDF', email='coordpdf@unifei.edu.br', tipo='docente',
        )
        self.user = _criar_usuario('doc_pdf', Perfil.PERFIL_DOCENTE, pessoa)
        self.projeto = Projeto.objects.create(
            codigo='PVDI889-2026',
            titulo='Projeto a submeter',
            resumo='Resumo do projeto a submeter para avaliação.',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=pessoa,
        )
        self.url = reverse('projeto_submeter', kwargs={'pk': self.projeto.pk})
        self.client.login(username='doc_pdf', password='x')

    def test_submeter_sem_pdf_e_bloqueado(self):
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'Anexe o PDF do projeto')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'nao_submetido')

    def test_submeter_com_pdf_envia(self):
        anexar_pdf(self.projeto)
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, 'enviado para avaliação por pares')
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.status_avaliacao, 'submetido')


class ArquivoProjetoTests(MediaTemporariaMixin, TestCase):
    """A rota do PDF aplica a mesma visibilidade da tela de detalhe."""

    def setUp(self):
        super().setUp()
        pessoa = Pessoa.objects.create(
            nome='Coordenador Arquivo', email='coordarq@unifei.edu.br', tipo='docente',
        )
        self.outro_aluno = Pessoa.objects.create(
            nome='Aluno de Fora', email='fora@alunos.edu.br', tipo='aluno',
            matricula='20269999',
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Participante', email='part@alunos.edu.br', tipo='aluno',
            matricula='20268888',
        )
        self.projeto = Projeto.objects.create(
            codigo='PVDI890-2026',
            titulo='Projeto com PDF',
            resumo='Resumo do projeto com documento anexado.',
            data_registro=date.today(),
            data_inicio=date.today(),
            coordenador=pessoa,
        )
        anexar_pdf(self.projeto, nome='projeto-anexo.pdf')
        MembroEquipe.objects.create(
            projeto=self.projeto, pessoa=self.aluno,
            funcao='discente', data_entrada=date.today(),
        )
        self.url = reverse('projeto_arquivo', kwargs={'pk': self.projeto.pk})

    def _usuario(self, username, perfil, pessoa=None):
        _criar_usuario(username, perfil, pessoa)
        self.client.login(username=username, password='x')

    def test_exige_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/contas/entrar/', response.url)

    def test_tecnico_baixa_o_pdf(self):
        self._usuario('tec_arq', Perfil.PERFIL_TECNICO)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('projeto-anexo.pdf', response['Content-Disposition'])

    def test_aluno_participante_baixa_o_pdf(self):
        self._usuario('alu_arq', Perfil.PERFIL_ALUNO, self.aluno)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_aluno_fora_do_projeto_nao_baixa(self):
        self._usuario('alu_fora', Perfil.PERFIL_ALUNO, self.outro_aluno)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_projeto_sem_arquivo_retorna_404(self):
        sem_pdf = Projeto.objects.create(
            codigo='PVDI891-2026',
            titulo='Projeto sem documento',
            data_registro=date.today(),
            data_inicio=date.today(),
        )
        self._usuario('tec_arq2', Perfil.PERFIL_TECNICO)
        url = reverse('projeto_arquivo', kwargs={'pk': sem_pdf.pk})
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_detalhe_exibe_resumo_e_link_do_pdf(self):
        self._usuario('tec_arq3', Perfil.PERFIL_TECNICO)
        response = self.client.get(
            reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}),
        )
        self.assertContains(response, 'Resumo do projeto com documento anexado.')
        self.assertContains(response, 'Abrir o PDF do projeto')
        self.assertContains(response, self.url)


class BuscaProjetoPorResumoTests(TestCase):
    """A lista de projetos busca por código, título e resumo."""

    def setUp(self):
        self.user = _criar_usuario('tec_busca', Perfil.PERFIL_TECNICO)
        self.alvo = Projeto.objects.create(
            codigo='PVDI892-2026',
            titulo='Biossensores ambientais',
            resumo='Trata de biotecnologia aplicada à monitoração de rios.',
            data_registro=date.today(),
            data_inicio=date.today(),
        )
        self.outro = Projeto.objects.create(
            codigo='PVDI893-2026',
            titulo='Geometria de curvas',
            resumo='Área pura da matemática, sem relação com biotecnologia.',
            data_registro=date.today(),
            data_inicio=date.today(),
        )
        self.url = reverse('projetos_lista')
        self.client.login(username='tec_busca', password='x')

    def test_busca_por_resumo(self):
        response = self.client.get(self.url, {'q': 'biotecnologia aplicada'})
        self.assertContains(response, self.alvo.codigo)
        self.assertNotContains(response, self.outro.codigo)

    def test_busca_por_codigo(self):
        response = self.client.get(self.url, {'q': 'PVDI893'})
        self.assertContains(response, self.outro.codigo)
        self.assertNotContains(response, self.alvo.codigo)

    def test_busca_sem_resultado(self):
        response = self.client.get(self.url, {'q': 'texto-que-nao-existe'})
        self.assertNotContains(response, self.alvo.codigo)
        self.assertNotContains(response, self.outro.codigo)

    def test_placeholder_sugere_resumo(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Código, título ou resumo')
