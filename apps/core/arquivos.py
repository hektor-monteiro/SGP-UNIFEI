"""Envio de arquivos enviados pelo usuário (upload) com controle de acesso.

Os PDFs nunca são servidos por /media/ (rota pública): cada view chama
`servir_pdf` depois de aplicar as MESMAS permissões da tela de detalhe —
além do `login_required`, o conteúdo do arquivo obedece à visibilidade
do objeto (LGPD e perfis do sistema).
"""
from pathlib import Path

from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.utils.text import get_valid_filename


def apagar_arquivo(nome: str) -> None:
    """Remove do storage o arquivo enviado `nome` (substituído ou excluído).

    Silencioso por design: um arquivo que já não existe no disco não pode
    quebrar a exclusão do registro.
    """
    if not nome:
        return
    try:
        if default_storage.exists(nome):
            default_storage.delete(nome)
    except OSError:
        pass


def servir_pdf(caminho, nome_original=None) -> FileResponse:
    """Responde com o PDF armazenado em `caminho`.

    - 404 se o arquivo não existir mais no disco;
    - nome exibido saneado (`get_valid_filename` — sem traversal);
    - `Content-Disposition: inline` (o navegador exibe o PDF) e
      `X-Content-Type-Options: nosniff` para impedir que o navegador
      reinterprete o conteúdo como outro tipo.
    """
    if not caminho or not Path(caminho).exists():
        raise Http404('Arquivo não encontrado.')

    nome = get_valid_filename(nome_original or Path(caminho).name)
    resposta = FileResponse(
        open(caminho, 'rb'),
        content_type='application/pdf',
        filename=nome,
    )
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta
