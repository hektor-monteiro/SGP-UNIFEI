"""Utilitários de teste para upload de PDF.

Os testes que enviam arquivo usam MEDIA_ROOT temporário (senão os PDFs
cairiam em media/ do projeto) e um PDF mínimo de verdade — assinatura
`%PDF-` presente, o suficiente para passar pelo validador do servidor.
"""
import tempfile

from django.core.files.base import ContentFile
from django.test import override_settings

PDF_EXEMPLO = (
    b'%PDF-1.4\n'
    b'1 0 obj\n<< /Type /Catalog >>\nendobj\n'
    b'trailer\n<< /Root 1 0 R >>\n'
    b'%%EOF\n'
)


class MediaTemporariaMixin:
    """Aponta MEDIA_ROOT para um diretório temporário durante o teste."""

    def setUp(self):
        super().setUp()
        patcher = override_settings(MEDIA_ROOT=tempfile.mkdtemp())
        patcher.enable()
        self.addCleanup(patcher.disable)


def anexar_pdf(objeto, nome='documento.pdf', campo='arquivo_pdf'):
    """Grava um PDF mínimo no campo de arquivo do objeto (e persiste)."""
    getattr(objeto, campo).save(nome, ContentFile(PDF_EXEMPLO), save=True)
    return objeto
