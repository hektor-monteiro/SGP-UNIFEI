"""Gerador mínimo de PDF para os dados de demonstração.

Sem dependências externas: monta um PDF 1.4 válido (objeto, xref e
trailer) com um título e parágrafos em Helvetica. Usado pelo
`populate_demo` para anexar um documento real a planos, relatórios e
projetos submetidos — quem abrir o Pacote Docker vê o upload funcionando
como em produção.
"""

# Margem superior e passo de linha do texto (pontos do PDF)
_ORIGEM_Y = 750
_PASSO = 18


def _escape(texto: str) -> str:
    """Escapa os caracteres reservados de string do formato PDF."""
    return (
        texto.replace('\\', '\\\\')
        .replace('(', '\\(')
        .replace(')', '\\)')
    )


def gerar_pdf(titulo: str, paragrafos=()) -> bytes:
    """Retorna os bytes de um PDF com `titulo` e `paragrafos` na página 1."""
    operacoes = ['BT', '/F1 14 Tf', f'72 {_ORIGEM_Y} Td', f'{_PASSO} TL']
    operacoes.append(f'({_escape(str(titulo)[:90])}) Tj T*')
    operacoes.append('/F1 11 Tf')
    for paragrafo in paragrafos:
        operacoes.append(f'({_escape(str(paragrafo)[:95])}) Tj T*')
    operacoes.append('ET')
    conteudo = '\n'.join(operacoes).encode('latin-1', 'replace')

    objetos = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        (
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
            b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>'
        ),
        # /Encoding explícito: sem ele o visualizador interpreta os bytes com
        # a codificação padrão da fonte e os acentos saem errados (á → Æ)
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica '
        b'/Encoding /WinAnsiEncoding >>',
        b'<< /Length '
        + str(len(conteudo)).encode()
        + b' >>\nstream\n'
        + conteudo
        + b'\nendstream',
    ]

    partes = [b'%PDF-1.4\n']
    offsets = []
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(sum(len(parte) for parte in partes))
        partes.append(f'{numero} 0 obj\n'.encode() + objeto + b'\nendobj\n')

    xref = sum(len(parte) for parte in partes)
    partes.append(b'xref\n')
    partes.append(f'0 {len(objetos) + 1}\n'.encode())
    partes.append(b'0000000000 65535 f \n')
    for offset in offsets:
        partes.append(f'{offset:010d} 00000 n \n'.encode())
    partes.append(
        f'trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n'.encode()
    )
    partes.append(f'startxref\n{xref}\n%%EOF\n'.encode())
    return b''.join(partes)
