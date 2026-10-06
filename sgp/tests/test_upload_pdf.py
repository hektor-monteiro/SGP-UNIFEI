"""Testes da base de upload de PDF (validador e envio seguro).

Cobre a M1 da migração para documentos em PDF: `MEDIA_ROOT`/`MEDIA_URL`,
`apps.core.validators.validar_pdf` (extensão + tamanho + assinatura
mágica) e `apps.core.arquivos.servir_pdf` (envio com nome saneado e
sem sniffing — os arquivos nunca são servidos por /media público).
"""
import tempfile
from pathlib import Path
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings

from apps.core.arquivos import servir_pdf
from apps.core.validators import (
    ASSINATURA_PDF,
    TAMANHO_MAXIMO_PDF,
    TAMANHO_MAXIMO_PDF_MB,
    validar_pdf,
)

PDF_VALIDO = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n'


def _pdf(nome='documento.pdf', conteudo=PDF_VALIDO):
    """Arquivo enviado simulado com conteúdo de PDF."""
    return SimpleUploadedFile(nome, conteudo)


class ValidadorPdfTests(SimpleTestCase):
    """Validação do arquivo enviado no servidor."""

    def test_aceita_pdf_valido(self):
        validar_pdf(_pdf())  # não levanta exceção

    def test_aceita_com_caixa_mista(self):
        validar_pdf(_pdf(nome='Relatorio Final.PDF'))

    def test_rejeita_extensao_diferente(self):
        with self.assertRaises(ValidationError) as ctx:
            validar_pdf(SimpleUploadedFile('relatorio.docx', b'PK\x03\x04'))
        self.assertIn('PDF', str(ctx.exception))

    def test_rejeita_assinatura_invalida(self):
        """Extensão .pdf mente: o conteúdo precisa começar com %PDF-."""
        with self.assertRaises(ValidationError):
            validar_pdf(_pdf(conteudo=b'<html><body>oi</body></html>'))

    def test_rejeita_pdf_truncado(self):
        with self.assertRaises(ValidationError):
            validar_pdf(_pdf(conteudo=b'%PD'))

    def test_rejeita_arquivo_acima_do_limite(self):
        with mock.patch('apps.core.validators.TAMANHO_MAXIMO_PDF', 10):
            with self.assertRaises(ValidationError) as ctx:
                validar_pdf(_pdf(conteudo=ASSINATURA_PDF + b'0' * 64))
        self.assertIn('limite', str(ctx.exception))

    def test_arquivo_ausente_e_ignorado(self):
        """Obrigatoriedade é decisão do campo/regra de submissão."""
        validar_pdf(None)
        validar_pdf('')

    def test_assinatura_e_pdf_minusculo(self):
        """Qualquer PDF começa com %PDF- (5 bytes)."""
        self.assertEqual(ASSINATURA_PDF, b'%PDF-')
        self.assertEqual(TAMANHO_MAXIMO_PDF, TAMANHO_MAXIMO_PDF_MB * 1024 * 1024)


class ConfiguracaoMediaTests(SimpleTestCase):
    """MEDIA_ROOT/URL configurados fora do código-fonte."""

    def test_media_root_fora_do_codigo(self):
        from django.conf import settings

        self.assertTrue(str(settings.MEDIA_ROOT).endswith('media'))
        self.assertNotEqual(settings.MEDIA_ROOT, settings.BASE_DIR / 'static')

    def test_media_url(self):
        from django.conf import settings

        # Django normaliza para começar e terminar com barra
        self.assertTrue(settings.MEDIA_URL.startswith('/'))
        self.assertTrue(settings.MEDIA_URL.endswith('media/'))


class ServirPdfTests(SimpleTestCase):
    """`servir_pdf`: nome saneado, content-type correto e 404 sem arquivo."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.caminho = Path(self.dir) / 'plano.pdf'
        self.caminho.write_bytes(PDF_VALIDO)

    def test_responde_pdf_inline_sem_sniffing(self):
        resposta = servir_pdf(str(self.caminho))
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertEqual(resposta['X-Content-Type-Options'], 'nosniff')
        self.assertIn('inline', resposta['Content-Disposition'])
        self.assertIn('plano.pdf', resposta['Content-Disposition'])
        resposta.close()

    def test_nome_original_e_saneado(self):
        resposta = servir_pdf(str(self.caminho), nome_original='../../pasta/plano.pdf')
        nome = resposta['Content-Disposition']
        resposta.close()
        self.assertIn('plano.pdf', nome)
        # sem separadores de caminho: nada de traversal no header
        self.assertNotIn('/', nome)
        self.assertNotIn('\\', nome)

    def test_arquivo_inexistente_retorna_404(self):
        from django.http import Http404

        with self.assertRaises(Http404):
            servir_pdf(str(Path(self.dir) / 'nao-existe.pdf'))

    def test_caminho_vazio_retorna_404(self):
        from django.http import Http404

        with self.assertRaises(Http404):
            servir_pdf('')

    @override_settings(MEDIA_ROOT='/tmp')
    def test_compativel_com_media_root(self):
        """`servir_pdf` é usado com `objeto.arquivo_pdf.path` (MEDIA_ROOT)."""
        from django.conf import settings

        caminho = str(Path(settings.MEDIA_ROOT) / 'qualquer.pdf')
        self.assertTrue(caminho.startswith('/'))


class MediaIgnoradaPeloDockerTests(SimpleTestCase):
    """Os uploads não podem entrar na imagem nem no repositório."""

    def test_dockerignore_cobre_media(self):
        conteudo = Path('.dockerignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('media', [linha.strip() for linha in conteudo])

    def test_gitignore_cobre_media(self):
        conteudo = Path('.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('media/', [linha.strip() for linha in conteudo])

    def test_compose_producao_tem_volume_de_media(self):
        conteudo = Path('docker-compose.prod.yml').read_text(encoding='utf-8')
        self.assertIn('/app/media', conteudo)
        self.assertIn('media_data:', conteudo)
