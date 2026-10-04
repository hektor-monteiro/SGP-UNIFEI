"""Views do módulo de Planos de Trabalho.

Regras de acesso:
- Lista/Detalhe: aluno vê apenas os próprios; docente/técnico: todos.
- Criação: aluno (própria bolsa sem plano), docente (bolsas dos projetos que
  coordena), técnico+ (qualquer bolsa).
- Edição: aluno só os próprios em rascunho/reprovado e sem mudar status;
  docente: planos dos projetos que coordena (com status); técnico+ sempre.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.bolsas.models import Bolsa
from apps.core.models import Perfil
from apps.core.permissions import perfil_de, pode_gerir

from .forms import PlanoTrabalhoForm
from .models import PlanoTrabalho

# Status em que o aluno ainda pode editar o próprio plano
STATUS_EDITAVEIS_PELO_ALUNO = ('rascunho', 'reprovado')


def _planos_visiveis(user):
    """Planos visíveis: aluno vê apenas os próprios."""
    planos = PlanoTrabalho.objects.select_related('aluno', 'bolsa', 'projeto')
    perfil = perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        return planos.filter(aluno=perfil.pessoa) if perfil.pessoa else planos.none()
    return planos


def _bolsas_para(user, sem_plano=False):
    """Bolsas disponíveis para vincular ao plano.

    Aluno: as próprias. Docente: as de seus projetos. Técnico+/superusuário: todas.
    `sem_plano=True` restringe a bolsas ainda sem plano (criação).
    """
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        bolsas = Bolsa.objects.all()
    elif perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        bolsas = (
            Bolsa.objects.filter(aluno=perfil.pessoa)
            if perfil.pessoa else Bolsa.objects.none()
        )
    elif perfil and perfil.pessoa:
        bolsas = Bolsa.objects.filter(projeto__coordenador=perfil.pessoa)
    else:
        bolsas = Bolsa.objects.none()
    if sem_plano:
        bolsas = bolsas.filter(plano_trabalho__isnull=True)
    return bolsas.select_related('aluno', 'projeto', 'modalidade')


def _pode_editar(user, plano) -> bool:
    """Edita técnico+, coordenador do projeto, ou o próprio aluno (restrito)."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    if perfil and perfil.pessoa:
        if perfil.perfil == Perfil.PERFIL_ALUNO:
            return (
                plano.aluno_id == perfil.pessoa.id
                and plano.status in STATUS_EDITAVEIS_PELO_ALUNO
            )
        return plano.projeto.coordenador_id == perfil.pessoa.id
    return False


def _muda_status(user, plano) -> bool:
    """Só técnico+ ou o coordenador do projeto alteram o status."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    return bool(
        perfil and perfil.pessoa
        and plano.projeto.coordenador_id == perfil.pessoa.id
    )


@login_required
@never_cache
def lista(request):
    """Lista de planos com filtros por status e busca por título."""
    planos = _planos_visiveis(request.user)

    status = request.GET.get('status', '')
    busca = request.GET.get('q', '')
    if status:
        planos = planos.filter(status=status)
    if busca:
        planos = planos.filter(titulo__icontains=busca)

    perfil = perfil_de(request.user)
    gerir = pode_gerir(perfil)
    if gerir:
        editaveis = set()
    elif perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        editaveis = set(
            planos.filter(status__in=STATUS_EDITAVEIS_PELO_ALUNO).values_list('pk', flat=True)
        )
    elif perfil and perfil.pessoa:
        editaveis = set(
            planos.filter(projeto__coordenador=perfil.pessoa).values_list('pk', flat=True)
        )
    else:
        editaveis = set()

    contexto = {
        'planos': planos.order_by('-criado_em'),
        'filtros': {'status': status, 'q': busca},
        'status_choices': PlanoTrabalho._meta.get_field('status').choices,
        'pode_criar': _bolsas_para(request.user, sem_plano=True).exists(),
        'pode_gerir': gerir,
        'editaveis': editaveis,
    }
    return render(request, 'planos/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe do plano com bolsa e projeto do docente."""
    plano = get_object_or_404(
        PlanoTrabalho.objects.select_related(
            'aluno', 'projeto', 'bolsa', 'bolsa__modalidade',
        ),
        pk=pk,
    )

    perfil = perfil_de(request.user)
    # Aluno só vê os próprios planos
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa or plano.aluno_id != perfil.pessoa.id:
            raise PermissionDenied

    contexto = {
        'plano': plano,
        'pode_editar': _pode_editar(request.user, plano),
        'muda_status': _muda_status(request.user, plano),
    }
    return render(request, 'planos/detalhe.html', contexto)


@login_required
@never_cache
def novo(request):
    """Criação de plano de trabalho (aluno para a própria bolsa, etc.)."""
    perfil_de(request.user)  # usuários sem perfil → 403
    bolsas = _bolsas_para(request.user, sem_plano=True)
    perfil = perfil_de(request.user)
    pode_mudar = pode_gerir(perfil)

    # Pré-seleciona a bolsa vinda de ?bolsa=<id> (link na página da bolsa)
    inicial = {}
    bolsa_id = request.GET.get('bolsa')
    if bolsa_id:
        inicial['bolsa'] = bolsa_id

    if request.method == 'POST':
        form = PlanoTrabalhoForm(
            request.POST, bolsas=bolsas, pode_mudar_status=pode_mudar,
        )
        if form.is_valid():
            plano = form.save()
            messages.success(request, 'Plano de trabalho criado com sucesso.')
            return redirect('plano_detalhe', pk=plano.pk)
    else:
        form = PlanoTrabalhoForm(
            initial=inicial, bolsas=bolsas, pode_mudar_status=pode_mudar,
        )

    return render(request, 'planos/form.html', {
        'form': form,
        'titulo': 'Novo plano de trabalho',
        'plano': None,
    })


@login_required
@never_cache
def editar(request, pk):
    """Edição de plano de trabalho."""
    plano = get_object_or_404(PlanoTrabalho, pk=pk)
    if not _pode_editar(request.user, plano):
        raise PermissionDenied

    bolsas = _bolsas_para(request.user)
    pode_mudar = _muda_status(request.user, plano)

    if request.method == 'POST':
        form = PlanoTrabalhoForm(
            request.POST, instance=plano,
            bolsas=bolsas, pode_mudar_status=pode_mudar,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Plano de trabalho atualizado com sucesso.')
            return redirect('plano_detalhe', pk=plano.pk)
    else:
        form = PlanoTrabalhoForm(
            instance=plano, bolsas=bolsas, pode_mudar_status=pode_mudar,
        )

    return render(request, 'planos/form.html', {
        'form': form,
        'titulo': f'Editar plano: {plano.titulo}',
        'plano': plano,
    })
