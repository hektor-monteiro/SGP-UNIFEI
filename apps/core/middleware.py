"""Auditoria LGPD (§6): registra quem acessou o quê e quando.

- Escritas (POST/PUT/PATCH) e exclusões (DELETE ou caminhos de exclusão)
  de usuários autenticados;
- Acessos negados (401/403), inclusive de anônimos;
- Login/logout via sinais de autenticação.

Leituras comuns (GET) não são registradas para evitar ruído excessivo na
tabela. A auditoria nunca derruba a requisição do usuário: falhas são
registradas no log da aplicação.
"""
import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import LogAuditoria

logger = logging.getLogger(__name__)

_CAMINHOS_IGNORADOS = ('/static/', '/media/')
# Rotas de sessão: login/logout já são auditados pelos sinais
_CAMINHOS_SESSAO = ('/contas/entrar/', '/contas/sair/')


def _ip_da_requisicao(request):
    """IP do cliente, considerando proxy reverso (X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def _registrar(acao, request, usuario, status, view=''):
    """Cria o registro de auditoria (sempre com dados básicos preenchidos).

    `request` pode ser um HttpRequest "pelado" (ex.: `Client.login()`
    do Django, sem method/path) — por isso os `or ''`.
    """
    LogAuditoria.objects.create(
        usuario=usuario,
        acao=acao,
        caminho=(getattr(request, 'path', '') or '')[:200],
        view=view[:200],
        metodo=getattr(request, 'method', '') or '',
        status=status,
        ip=_ip_da_requisicao(request),
    )


class AuditoriaMiddleware:
    """Registra escritas, exclusões e acessos negados no log de auditoria."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._registrar_resposta(request, response)
        except Exception:
            # A auditoria nunca deve derrubar a requisição do usuário
            logger.exception('Falha ao registrar log de auditoria')
        return response

    def _registrar_resposta(self, request, response):
        if request.path.startswith(_CAMINHOS_IGNORADOS):
            return

        status = response.status_code
        usuario = (
            request.user if request.user.is_authenticated else None
        )
        view = ''
        if getattr(request, 'resolver_match', None):
            view = request.resolver_match.view_name or ''

        # Acessos negados sempre são auditados (inclusive anônimos)
        if status in (401, 403):
            _registrar('acesso_negado', request, usuario, status, view)
            return

        # Anônimos: só interessam as negações (acima)
        if usuario is None:
            return

        metodo = request.method
        if metodo == 'DELETE' or (
            metodo in ('POST', 'PUT', 'PATCH') and 'excluir' in request.path
        ):
            _registrar('exclusao', request, usuario, status, view)
        elif metodo in ('POST', 'PUT', 'PATCH'):
            if request.path in _CAMINHOS_SESSAO:
                return  # login/logout já registrados pelos sinais
            _registrar('escrita', request, usuario, status, view)


@receiver(user_logged_in)
def _registrar_login(sender, request, user, **kwargs):
    """Audita o login (o POST do formulário é anônimo — daí o sinal)."""
    _registrar('login', request, user, 200, 'login')


@receiver(user_logged_out)
def _registrar_logout(sender, request, user, **kwargs):
    """Audita o logout (user pode ser None se ninguém estava logado)."""
    if user is None:
        return
    _registrar('logout', request, user, 200, 'logout')
