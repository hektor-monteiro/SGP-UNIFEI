"""Views do módulo de Equipes (§3.8): gestão de membros dos projetos.

Permissões: técnicos+, superusuário e o coordenador do projeto.
Aluno e docente sem coordenação não gerenciam equipe.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.core.permissions import perfil_de, pode_gerir
from apps.projetos.models import Projeto

from .forms import MembroEquipeForm
from .models import MembroEquipe


def _pode_gerir(user, projeto) -> bool:
    """Superusuário/técnicos+ gerenciam tudo; coordenador, só o seu projeto."""
    perfil = perfil_de(user)  # superusuário → None; sem perfil → PermissionDenied
    if pode_gerir(perfil):
        return True
    return (
        perfil is not None
        and perfil.pessoa_id is not None
        and projeto.coordenador_id == perfil.pessoa_id
    )


@login_required
@never_cache
def membro_novo(request, projeto_pk):
    """Adiciona membro à equipe do projeto."""
    projeto = get_object_or_404(Projeto, pk=projeto_pk)
    if not _pode_gerir(request.user, projeto):
        raise PermissionDenied

    if request.method == 'POST':
        form = MembroEquipeForm(request.POST, projeto=projeto)
        if form.is_valid():
            membro = form.save()
            messages.success(
                request, f'{membro.pessoa.nome} adicionado à equipe.',
            )
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        form = MembroEquipeForm(projeto=projeto)

    return render(request, 'equipes/form.html', {
        'form': form,
        'titulo': 'Novo membro da equipe',
        'projeto': projeto,
    })


@login_required
@never_cache
def membro_editar(request, pk):
    """Edita membro de equipe (pessoa, função, período)."""
    membro = get_object_or_404(
        MembroEquipe.objects.select_related('projeto', 'pessoa'),
        pk=pk,
    )
    if not _pode_gerir(request.user, membro.projeto):
        raise PermissionDenied

    if request.method == 'POST':
        form = MembroEquipeForm(
            request.POST, instance=membro, projeto=membro.projeto,
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Membro da equipe atualizado.')
            return redirect('projeto_detalhe', pk=membro.projeto_id)
    else:
        form = MembroEquipeForm(instance=membro, projeto=membro.projeto)

    return render(request, 'equipes/form.html', {
        'form': form,
        'titulo': f'Editar membro — {membro.pessoa.nome}',
        'projeto': membro.projeto,
    })


@login_required
def membro_encerrar(request, pk):
    """Encerra o vínculo: data de saída = hoje e fica inativo (POST)."""
    membro = get_object_or_404(
        MembroEquipe.objects.select_related('projeto', 'pessoa'),
        pk=pk,
    )
    if not _pode_gerir(request.user, membro.projeto):
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('projeto_detalhe', pk=membro.projeto_id)

    if not membro.data_saida:
        membro.data_saida = timezone.localdate()
    membro.ativo = False
    membro.save()
    messages.success(request, f'Vínculo de {membro.pessoa.nome} encerrado.')
    return redirect('projeto_detalhe', pk=membro.projeto_id)


@login_required
def membro_excluir(request, pk):
    """Remove o membro da equipe (POST — para correção de cadastro)."""
    membro = get_object_or_404(
        MembroEquipe.objects.select_related('projeto', 'pessoa'),
        pk=pk,
    )
    if not _pode_gerir(request.user, membro.projeto):
        raise PermissionDenied
    if request.method != 'POST':
        return redirect('projeto_detalhe', pk=membro.projeto_id)

    projeto_pk = membro.projeto_id
    nome = membro.pessoa.nome
    membro.delete()
    messages.success(request, f'{nome} removido da equipe.')
    return redirect('projeto_detalhe', pk=projeto_pk)
