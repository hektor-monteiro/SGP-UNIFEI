"""Views do módulo de Bolsas.

Regras de acesso:
- Lista/Detalhe: todos os autenticados; aluno vê apenas as próprias bolsas.
- Criação: docente (somente em projetos que coordena), técnico, diretor, pro-reitor.
- Edição: coordenador do projeto da bolsa, técnico, diretor, pro-reitor.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.core.models import Perfil
from apps.core.permissions import perfil_de, perfil_required, pode_criar, pode_gerir
from apps.projetos.models import Projeto

from .forms import BolsaForm, ModalidadeBolsaForm
from .models import Bolsa, ModalidadeBolsa


def _pode_editar(user, bolsa) -> bool:
    """Edita quem pode gerir ou o coordenador do projeto da bolsa."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    if perfil and perfil.pessoa and bolsa.projeto.coordenador_id == perfil.pessoa.id:
        return True
    return False


def _projetos_para(user):
    """Queryset de projetos onde o usuário pode vincular bolsas.

    Retorna None = todos os projetos (técnico+).
    Docente: apenas projetos que coordena.
    """
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return None
    if perfil and perfil.pessoa:
        return Projeto.objects.filter(coordenador=perfil.pessoa)
    return Projeto.objects.none()


@login_required
@never_cache
def lista(request):
    """Lista de bolsas com filtros por status, modalidade e aluno."""
    bolsas = Bolsa.objects.select_related(
        'aluno', 'modalidade', 'projeto', 'fomentador',
    )
    perfil = perfil_de(request.user)

    # Aluno vê apenas as próprias bolsas
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        bolsas = (
            bolsas.filter(aluno=perfil.pessoa)
            if perfil.pessoa else bolsas.none()
        )

    status = request.GET.get('status', '')
    modalidade = request.GET.get('modalidade', '')
    busca = request.GET.get('q', '')

    if status:
        bolsas = bolsas.filter(status=status)
    if modalidade:
        bolsas = bolsas.filter(modalidade__sigla=modalidade)
    if busca:
        bolsas = bolsas.filter(aluno__nome__icontains=busca)

    # Quem pode editar cada bolsa da lista (docente: só as de seus projetos)
    gerir_todos = pode_gerir(perfil)
    if gerir_todos:
        editaveis = set()
    else:
        editaveis = (
            set(bolsas.filter(projeto__coordenador=perfil.pessoa).values_list('pk', flat=True))
            if perfil and perfil.pessoa else set()
        )

    contexto = {
        'bolsas': bolsas.order_by('-data_inicio'),
        'filtros': {'status': status, 'modalidade': modalidade, 'q': busca},
        'status_choices': Bolsa._meta.get_field('status').choices,
        'modalidades': ModalidadeBolsa.objects.filter(ativo=True),
        'pode_criar': pode_criar(request.user),
        'pode_gerir': gerir_todos,
        'editaveis': editaveis,
    }
    return render(request, 'bolsas/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe da bolsa."""
    bolsa = get_object_or_404(
        Bolsa.objects.select_related('aluno', 'modalidade', 'projeto', 'fomentador'),
        pk=pk,
    )

    perfil = perfil_de(request.user)
    # Aluno só vê as próprias bolsas
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa or bolsa.aluno_id != perfil.pessoa.id:
            raise PermissionDenied

    contexto = {
        'bolsa': bolsa,
        'pode_editar': _pode_editar(request.user, bolsa),
    }
    return render(request, 'bolsas/detalhe.html', contexto)


@login_required
@never_cache
def nova(request):
    """Criação de bolsa (aluno não cria)."""
    if not pode_criar(request.user):
        raise PermissionDenied

    projetos = _projetos_para(request.user)

    if request.method == 'POST':
        form = BolsaForm(request.POST, projetos=projetos)
        if form.is_valid():
            bolsa = form.save()
            messages.success(request, f'Bolsa de {bolsa.aluno.nome} criada com sucesso.')
            return redirect('bolsa_detalhe', pk=bolsa.pk)
    else:
        form = BolsaForm(projetos=projetos)

    return render(request, 'bolsas/form.html', {
        'form': form,
        'titulo': 'Nova bolsa',
    })


@login_required
@never_cache
def editar(request, pk):
    """Edição de bolsa."""
    bolsa = get_object_or_404(Bolsa, pk=pk)
    if not _pode_editar(request.user, bolsa):
        raise PermissionDenied

    projetos = _projetos_para(request.user)

    if request.method == 'POST':
        form = BolsaForm(request.POST, instance=bolsa, projetos=projetos)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bolsa atualizada com sucesso.')
            return redirect('bolsa_detalhe', pk=bolsa.pk)
    else:
        form = BolsaForm(instance=bolsa, projetos=projetos)

    return render(request, 'bolsas/form.html', {
        'form': form,
        'titulo': f'Editar bolsa de {bolsa.aluno.nome}',
    })


# --------------------------------------------------------------------------
# Modalidades de bolsa (configuração pelo técnico — requisito §3.2)
# --------------------------------------------------------------------------

@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
@never_cache
def modalidade_lista(request):
    """Lista de modalidades com nº de bolsas vinculadas (técnico+)."""
    modalidades = ModalidadeBolsa.objects.annotate(
        total_bolsas=Count('bolsa'),
    )
    return render(request, 'bolsas/modalidades.html', {
        'modalidades': modalidades,
    })


@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
def modalidade_nova(request):
    """Criação de modalidade (técnico+)."""
    if request.method == 'POST':
        form = ModalidadeBolsaForm(request.POST)
        if form.is_valid():
            modalidade = form.save()
            messages.success(request, f'Modalidade {modalidade.sigla} criada com sucesso.')
            return redirect('modalidades_lista')
    else:
        form = ModalidadeBolsaForm()

    return render(request, 'bolsas/modalidade_form.html', {
        'form': form,
        'titulo': 'Nova modalidade',
    })


@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
def modalidade_editar(request, pk):
    """Edição de modalidade (técnico+)."""
    modalidade = get_object_or_404(ModalidadeBolsa, pk=pk)

    if request.method == 'POST':
        form = ModalidadeBolsaForm(request.POST, instance=modalidade)
        if form.is_valid():
            form.save()
            messages.success(request, f'Modalidade {modalidade.sigla} atualizada com sucesso.')
            return redirect('modalidades_lista')
    else:
        form = ModalidadeBolsaForm(instance=modalidade)

    return render(request, 'bolsas/modalidade_form.html', {
        'form': form,
        'titulo': f'Editar modalidade {modalidade.sigla}',
    })
