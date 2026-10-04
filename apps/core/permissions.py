"""Decoradores de autorização baseados no perfil de acesso.

Hierarquia: aluno < docente < tecnico < diretor < proreitor

Uso:
    @perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
    def minha_view(request):
        ...
"""
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .models import Perfil


def _perfil_do_usuario(user):
    """Retorna o Perfil do usuário ou None."""
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return None  # superusuário tem acesso total
    try:
        return user.perfil
    except Perfil.DoesNotExist:
        return None


def perfil_de(user):
    """Retorna o Perfil do usuário para as views decidirem acesso.

    None = superusuário (acesso total). Usuário autenticado SEM perfil
    recebe PermissionDenied — assim não ganha acesso por engano.
    """
    if user.is_superuser:
        return None
    try:
        return user.perfil
    except Perfil.DoesNotExist:
        raise PermissionDenied('Seu usuário não possui perfil de acesso. Procure a DIP.')


def pode_gerir(perfil) -> bool:
    """Superusuário (perfil None), técnico, diretor e pro-reitor gerenciam todos os processos."""
    return perfil is None or perfil.pelo_menos(Perfil.PERFIL_TECNICO)


def pode_criar(user) -> bool:
    """Docente ou técnico+ pode criar registros (aluno não cria)."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    return perfil is not None and perfil.perfil == Perfil.PERFIL_DOCENTE


def perfil_required(*perfis):
    """Exige que o usuário autenticado possua um dos perfis informados.

    Superusuários sempre têm acesso. Usuários sem Perfil são bloqueados.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            perfil = _perfil_do_usuario(request.user)
            if perfil and perfil.perfil in perfis:
                return view_func(request, *args, **kwargs)
            return render(request, 'core/403.html', status=403)
        return wrapper
    return decorator


def nivel_minimo(perfil_minimo):
    """Exige nível hierárquico igual ou superior ao informado.

    Exemplo: @nivel_minimo(Perfil.PERFIL_DIRETOR)
    aceita diretor e pro-reitor (e superusuários).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            perfil = _perfil_do_usuario(request.user)
            if perfil and perfil.pelo_menos(perfil_minimo):
                return view_func(request, *args, **kwargs)
            return render(request, 'core/403.html', status=403)
        return wrapper
    return decorator
