"""Views do módulo de Editais.

Fluxo de vida (requisito §3.1):
    rascunho → publicado → em_andamento → encerrado
                 (qualquer status operacional pode ir para cancelado)

Permissões:
- Lista/Detalhe: todos os autenticados (editais são informativos).
- Criação/Edição: técnico, diretor, pro-reitor (o técnico cria).
- Publicar/validar: SOMENTE diretor ou pro-reitor (requisito: "Técnico cria,
  Diretor/Pro-reitor valida") — carimba validado_por/data_validacao.
- Iniciar/Encerrar/Cancelar: técnico+.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.utils.timezone import now

from apps.core.models import Perfil
from apps.core.permissions import perfil_de, pode_gerir
from apps.bolsas.models import ModalidadeBolsa

from .forms import EditalForm
from .models import Edital

# Ações do fluxo: origens permitidas, destino, nível mínimo e rótulo
ACOES = {
    'publicar': {
        'origens': ('rascunho',),
        'destino': 'publicado',
        'nivel': Perfil.PERFIL_DIRETOR,
        'rotulo': 'Publicar e validar',
        'mensagem': 'publicado e validado',
    },
    'iniciar': {
        'origens': ('publicado',),
        'destino': 'em_andamento',
        'nivel': Perfil.PERFIL_TECNICO,
        'rotulo': 'Iniciar execução',
        'mensagem': 'em andamento',
    },
    'encerrar': {
        'origens': ('publicado', 'em_andamento'),
        'destino': 'encerrado',
        'nivel': Perfil.PERFIL_TECNICO,
        'rotulo': 'Encerrar',
        'mensagem': 'encerrado',
    },
    'cancelar': {
        'origens': ('rascunho', 'publicado', 'em_andamento'),
        'destino': 'cancelado',
        'nivel': Perfil.PERFIL_TECNICO,
        'rotulo': 'Cancelar edital',
        'mensagem': 'cancelado',
    },
}


def _pode_executar(user, acao: str) -> bool:
    """Superusuário sempre; senão, nível hierárquico mínimo da ação."""
    perfil = perfil_de(user)
    if perfil is None:
        return True
    return perfil.pelo_menos(ACOES[acao]['nivel'])


@login_required
@never_cache
def lista(request):
    """Lista de editais com filtros por status e modalidade."""
    editais = Edital.objects.select_related('modalidade', 'criado_por', 'validado_por')

    status = request.GET.get('status', '')
    modalidade = request.GET.get('modalidade', '')
    busca = request.GET.get('q', '')

    if status:
        editais = editais.filter(status=status)
    if modalidade:
        editais = editais.filter(modalidade__sigla=modalidade)
    if busca:
        editais = editais.filter(titulo__icontains=busca)

    perfil = perfil_de(request.user)
    contexto = {
        'editais': editais,
        'filtros': {'status': status, 'modalidade': modalidade, 'q': busca},
        'status_choices': Edital._meta.get_field('status').choices,
        'modalidades': ModalidadeBolsa.objects.filter(ativo=True),
        'pode_gerir': pode_gerir(perfil),
    }
    return render(request, 'editais/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe do edital com as ações disponíveis para o usuário."""
    edital = get_object_or_404(
        Edital.objects.select_related('modalidade', 'criado_por', 'validado_por'),
        pk=pk,
    )

    acoes_disponiveis = [
        (acao, cfg['rotulo'])
        for acao, cfg in ACOES.items()
        if edital.status in cfg['origens'] and _pode_executar(request.user, acao)
    ]

    contexto = {
        'edital': edital,
        'pode_gerir': pode_gerir(perfil_de(request.user)),
        'acoes_disponiveis': acoes_disponiveis,
        'fluxo': [rotulo for _, rotulo in Edital._meta.get_field('status').choices],
    }
    return render(request, 'editais/detalhe.html', contexto)


@login_required
@never_cache
def novo(request):
    """Criação de edital (técnico+, conforme requisito §3.1)."""
    perfil = perfil_de(request.user)
    if not pode_gerir(perfil):
        raise PermissionDenied

    if request.method == 'POST':
        form = EditalForm(request.POST)
        if form.is_valid():
            edital = form.save(commit=False)
            edital.criado_por = request.user
            edital.status = 'rascunho'  # precisa de validação do diretor
            edital.save()
            messages.success(request, f'Edital {edital.codigo} criado como rascunho. Aguarde a validação do diretor.')
            return redirect('edital_detalhe', pk=edital.pk)
    else:
        form = EditalForm()

    return render(request, 'editais/form.html', {
        'form': form,
        'titulo': 'Novo edital',
    })


@login_required
@never_cache
def editar(request, pk):
    """Edição de edital (técnico+). Status muda só pelas ações."""
    perfil = perfil_de(request.user)
    if not pode_gerir(perfil):
        raise PermissionDenied

    edital = get_object_or_404(Edital, pk=pk)

    if request.method == 'POST':
        form = EditalForm(request.POST, instance=edital)
        if form.is_valid():
            form.save()
            messages.success(request, f'Edital {edital.codigo} atualizado com sucesso.')
            return redirect('edital_detalhe', pk=edital.pk)
    else:
        form = EditalForm(instance=edital)

    return render(request, 'editais/form.html', {
        'form': form,
        'titulo': f'Editar edital {edital.codigo}',
    })


@login_required
@require_POST
def acao(request, pk, acao):
    """Executa uma transição do fluxo de vida do edital (somente POST)."""
    if acao not in ACOES:
        raise PermissionDenied

    edital = get_object_or_404(Edital, pk=pk)
    cfg = ACOES[acao]

    if not _pode_executar(request.user, acao):
        raise PermissionDenied

    if edital.status not in cfg['origens']:
        messages.error(
            request,
            f'Não é possível {acao} um edital com status '
            f'"{edital.get_status_display()}".',
        )
        return redirect('edital_detalhe', pk=edital.pk)

    edital.status = cfg['destino']
    if acao == 'publicar':
        edital.validado_por = request.user
        edital.data_validacao = now()
    edital.save()
    messages.success(request, f'Edital {edital.codigo}: {cfg["mensagem"]}.')
    return redirect('edital_detalhe', pk=edital.pk)
