"""Views do módulo de Projetos.

Regras de acesso:
- Lista/Detalhe: todos os autenticados; alunos veem apenas seus projetos.
- Criação: docente (vira coordenador), técnico, diretor, pro-reitor.
- Edição: coordenador do projeto, técnico, diretor, pro-reitor.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.core.models import Perfil
from apps.core.permissions import (
    perfil_de as _perfil_de,
    pode_criar as _pode_criar,
    pode_gerir as _pode_gerir,
)

from .forms import ProjetoForm
from .models import Projeto


def _pode_editar(user, projeto) -> bool:
    """Edita quem pode gerir ou o próprio coordenador."""
    perfil = _perfil_de(user)
    if _pode_gerir(perfil):
        return True
    if perfil and perfil.pessoa and projeto.coordenador_id == perfil.pessoa.id:
        return True
    return False


def _visiveis_para(user):
    """Projetos visíveis: aluno vê apenas os que participa."""
    projetos = Projeto.objects.select_related(
        'coordenador', 'instituicao', 'fomentador',
    )
    perfil = _perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if perfil.pessoa:
            return projetos.filter(membros__pessoa=perfil.pessoa).distinct()
        return projetos.none()
    return projetos


@login_required
@never_cache
def lista(request):
    """Lista de projetos com filtros por status e instituto."""
    projetos = _visiveis_para(request.user)

    status = request.GET.get('status', '')
    instituto = request.GET.get('instituto', '')
    busca = request.GET.get('q', '')

    if status:
        projetos = projetos.filter(status=status)
    if instituto:
        projetos = projetos.filter(instituicao__sigla=instituto)
    if busca:
        projetos = projetos.filter(titulo__icontains=busca)

    from apps.core.models import Instituicao

    # Quem pode editar cada projeto da lista (docente: só os seus)
    perfil = _perfil_de(request.user)
    pode_gerir = _pode_gerir(perfil)
    if pode_gerir:
        editaveis = set()
    else:
        editaveis = set(
            projetos.filter(coordenador=perfil.pessoa).values_list('pk', flat=True)
        ) if perfil and perfil.pessoa else set()

    contexto = {
        'projetos': projetos.order_by('-data_registro'),
        'filtros': {'status': status, 'instituto': instituto, 'q': busca},
        'status_choices': Projeto._meta.get_field('status').choices,
        'instituicoes': Instituicao.objects.filter(ativo=True),
        'pode_criar': _pode_criar(request.user),
        'pode_gerir': pode_gerir,
        'editaveis': editaveis,
    }
    return render(request, 'projetos/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe do projeto com equipe e bolsas."""
    projeto = get_object_or_404(
        Projeto.objects.select_related('coordenador', 'instituicao', 'fomentador', 'processo_sipac'),
        pk=pk,
    )

    perfil = _perfil_de(request.user)
    # Aluno só vê projetos dos quais participa
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not projeto.membros.filter(pessoa=perfil.pessoa).exists():
            raise PermissionDenied

    contexto = {
        'projeto': projeto,
        'membros': projeto.membros.select_related('pessoa').order_by('funcao'),
        'bolsas': projeto.bolsas.select_related('aluno', 'modalidade', 'fomentador').all(),
        'pode_editar': _pode_editar(request.user, projeto),
    }
    return render(request, 'projetos/detalhe.html', contexto)


@login_required
@never_cache
def novo(request):
    """Criação de projeto."""
    if not _pode_criar(request.user):
        raise PermissionDenied

    perfil = _perfil_de(request.user)
    docente_vinculado = (
        perfil is not None
        and perfil.perfil == Perfil.PERFIL_DOCENTE
        and perfil.pessoa
    )

    if request.method == 'POST':
        form = ProjetoForm(request.POST)
        if docente_vinculado:
            # Docente sempre coordena seu próprio projeto (campo desabilitado)
            form.fields['coordenador'].disabled = True
            form.fields["coordenador"].initial = perfil.pessoa.pk
        if form.is_valid():
            projeto = form.save()
            messages.success(request, f'Projeto {projeto.codigo} criado com sucesso.')
            return redirect('projeto_detalhe', pk=projeto.pk)
    else:
        form = ProjetoForm()
        if docente_vinculado:
            form.fields['coordenador'].disabled = True
            form.fields["coordenador"].initial = perfil.pessoa.pk

    return render(request, 'projetos/form.html', {
        'form': form,
        'titulo': 'Novo projeto',
    })


@login_required
@never_cache
def editar(request, pk):
    """Edição de projeto."""
    projeto = get_object_or_404(Projeto, pk=pk)
    if not _pode_editar(request.user, projeto):
        raise PermissionDenied

    perfil = _perfil_de(request.user)
    docente_vinculado = (
        perfil is not None
        and perfil.perfil == Perfil.PERFIL_DOCENTE
        and perfil.pessoa
    )

    if request.method == 'POST':
        form = ProjetoForm(request.POST, instance=projeto)
    else:
        form = ProjetoForm(instance=projeto)

    if docente_vinculado:
        # Docente edita os dados, mas NÃO transfere a coordenação (só técnico+)
        form.fields['coordenador'].disabled = True

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Projeto {projeto.codigo} atualizado com sucesso.')
        return redirect('projeto_detalhe', pk=projeto.pk)

    return render(request, 'projetos/form.html', {
        'form': form,
        'titulo': f'Editar projeto {projeto.codigo}',
    })
