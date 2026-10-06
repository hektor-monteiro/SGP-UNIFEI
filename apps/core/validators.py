"""Validadores de arquivos enviados pelo usuário (upload de PDF)."""
from django.core.exceptions import ValidationError

# Limite por arquivo: documentos acadêmicos costumam ficar bem abaixo disso.
TAMANHO_MAXIMO_PDF_MB = 15
TAMANHO_MAXIMO_PDF = TAMANHO_MAXIMO_PDF_MB * 1024 * 1024

# Assinatura mágica de todo PDF (primeiros 5 bytes do arquivo).
ASSINATURA_PDF = b'%PDF-'


def validar_pdf(arquivo) -> None:
    """Valida que o arquivo enviado é um PDF dentro do limite de tamanho.

    Três checagens, nesta ordem:
    1. extensão `.pdf` (mensagem amigável logo de cara);
    2. tamanho máximo (`TAMANHO_MAXIMO_PDF_MB` MB);
    3. assinatura mágica `%PDF-` — extensão e Content-Type podem mentir,
       a assinatura vem do próprio conteúdo.

    `arquivo` é um `UploadedFile` (ou equivalente com `name`, `size`,
    `read` e `seek`). Arquivo ausente é ignorado: a obrigatoriedade é
    decisão de quem usa o campo (`required=True` ou regra de submissão).
    """
    if not arquivo:
        return

    nome = (getattr(arquivo, 'name', '') or '').lower()
    if not nome.endswith('.pdf'):
        raise ValidationError('Anexe o documento em formato PDF (.pdf).')

    if arquivo.size > TAMANHO_MAXIMO_PDF:
        raise ValidationError(
            f'O arquivo excede o limite de {TAMANHO_MAXIMO_PDF_MB} MB.',
        )

    arquivo.seek(0)
    cabecalho = arquivo.read(len(ASSINATURA_PDF))
    arquivo.seek(0)
    if cabecalho != ASSINATURA_PDF:
        raise ValidationError(
            'O arquivo enviado não é um PDF válido (assinatura ilegível).',
        )
