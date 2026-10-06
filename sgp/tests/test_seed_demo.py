"""Teste do seed de demonstração (`populate_demo`) com documentos em PDF.

O Pacote Docker roda o seed na primeira subida; aqui garantimos que ele
termine sem erro e que planos/relatórios/projetos submetidos nasçam com
`resumo` preenchido e um PDF real anexado (validável pelo `validar_pdf`).
"""
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.core.validators import validar_pdf
from apps.projetos.models import Projeto
from apps.relatorios.models import PlanoTrabalho, Relatorio

# MEDIA_ROOT de teste: os PDFs do seed não podem cair em media/ do projeto
MEDIA_DE_TESTE = tempfile.mkdtemp(prefix='sgp-seed-')


@override_settings(MEDIA_ROOT=MEDIA_DE_TESTE)
class SeedDemoDocumentosTests(TestCase):
    """O seed gera resumos e anexa PDFs onde o fluxo exige documento."""

    @classmethod
    def setUpTestData(cls):
        call_command('populate_demo', stdout=StringIO())

    def test_projetos_nascem_com_resumo_e_pdf(self):
        projetos = Projeto.objects.all()
        self.assertTrue(projetos.exists())
        self.assertEqual(projetos.filter(resumo='').count(), 0)
        self.assertEqual(projetos.filter(arquivo_pdf='').count(), 0)

    def test_planos_submetidos_tem_pdf(self):
        submetidos = PlanoTrabalho.objects.exclude(status='rascunho')
        self.assertTrue(submetidos.exists())
        self.assertEqual(submetidos.filter(resumo='').count(), 0)
        self.assertEqual(submetidos.filter(arquivo_pdf='').count(), 0)

    def test_relatorios_submetidos_tem_pdf(self):
        submetidos = Relatorio.objects.exclude(status='rascunho')
        self.assertTrue(submetidos.exists())
        self.assertEqual(submetidos.filter(resumo='').count(), 0)
        self.assertEqual(submetidos.filter(arquivo_pdf='').count(), 0)

    def test_arquivos_gerados_sao_pdfs_validos(self):
        """A assinatura %PDF- passa no validador do servidor."""
        for projeto in Projeto.objects.exclude(arquivo_pdf=''):
            validar_pdf(projeto.arquivo_pdf)  # não levanta exceção
            projeto.arquivo_pdf.open('rb')
            self.assertTrue(projeto.arquivo_pdf.read(5).startswith(b'%PDF-'))
            projeto.arquivo_pdf.close()

    def test_fonte_declara_winansi_para_acentos(self):
        """Sem `/Encoding` o visualizador usa a codificação da fonte e os
        acentos saem errados (á → Æ, ç → ª) — o gerador precisa declarar
        WinAnsi, onde os bytes latin-1 gravados são os glifos certos."""
        projeto = Projeto.objects.exclude(arquivo_pdf='').first()
        projeto.arquivo_pdf.open('rb')
        conteudo = projeto.arquivo_pdf.read()
        projeto.arquivo_pdf.close()
        self.assertIn(b'/Encoding /WinAnsiEncoding', conteudo)

    def test_rascunho_fica_sem_pdf(self):
        """Só o que foi submetido/anexado tem documento (seed é econômico)."""
        rascunhos = PlanoTrabalho.objects.filter(status='rascunho')
        if rascunhos.exists():
            self.assertGreater(rascunhos.filter(arquivo_pdf='').count(), 0)
