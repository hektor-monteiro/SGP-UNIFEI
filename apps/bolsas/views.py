"""Views do módulo de Bolsas.

Regras de acesso:
- Lista/Detalhe: todos os autenticados; aluno vê apenas as próprias bolsas.
- Criação manual: somente técnico, diretor e pro-reitor — o fluxo normal é
  o docente indicar o aluno na proposta aprovada e o técnico implementar
  a bolsa a partir da indicação (requisito §3.5).
- Edição: coordenador do projeto da bolsa, técnico, diretor, pro-reitor.
- Indicações: téc+ veem todas; docente, as de suas propostas; implementar:
  somente téc+.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, F, OrderBy, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.timezone import localdate
from django.views.decorators.cache import never_cache

from apps.core.models import Perfil
from apps.core.permissions import perfil_de, perfil_required, pode_gerir
from apps.projetos.models import Projeto

from .forms import BolsaForm, ModalidadeBolsaForm
from .models import Bolsa, Indicacao, ModalidadeBolsa


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
        'pode_criar': gerir_todos,
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

    # Plano de trabalho vinculado (OneToOne) e quem pode criá-lo
    plano = getattr(bolsa, 'plano_trabalho', None)
    pode_criar_plano = plano is None and (
        _pode_editar(request.user, bolsa)
        or bool(
            perfil and perfil.perfil == Perfil.PERFIL_ALUNO
            and perfil.pessoa and bolsa.aluno_id == perfil.pessoa.id
        )
    )

    contexto = {
        'bolsa': bolsa,
        'pode_editar': _pode_editar(request.user, bolsa),
        'plano': plano,
        'pode_criar_plano': pode_criar_plano,
        'relatorios': bolsa.relatorios.all(),
    }
    return render(request, 'bolsas/detalhe.html', contexto)


@login_required
@never_cache
def nova(request):
    """Criação manual de bolsa (somente técnico+).

    No fluxo de cotas (§3.5), a bolsa nasce da indicação do docente e é
    implementada pelo técnico em `indicacao_implementar`; esta view cobre
    casos avulsos (sem edital).
    """
    if not pode_gerir(perfil_de(request.user)):
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
# Indicações de cotas (fluxo edital → proposta aprovada → bolsa, §3.5)
# --------------------------------------------------------------------------

@login_required
@never_cache
def indicacoes_lista(request):
    """Fila de indicações de cotas.

    Téc+ veem todas; docente, apenas as de propostas que submeteu;
    demais perfis (aluno) não acessam.
    """
    perfil = perfil_de(request.user)
    if pode_gerir(perfil):
        indicacoes = Indicacao.objects.all()
    elif (
        perfil is not None
        and perfil.perfil == Perfil.PERFIL_DOCENTE
        and perfil.pessoa_id
    ):
        indicacoes = Indicacao.objects.filter(
            proposta__submetido_por=perfil.pessoa,
        )
    else:
        raise PermissionDenied

    indicacoes = indicacoes.select_related(
        'proposta', 'proposta__edital', 'proposta__projeto',
        'aluno', 'indicado_por', 'bolsa',
    ).annotate(
        ordem=Case(When(status='pendente', then=Value(0)), default=Value(1)),
    ).order_by(
        # Prioridade automática: pendentes primeiro; dentro de cada grupo,
        # maior nota de avaliação por pares do projeto primeiro (§3.5)
        'ordem',
        OrderBy(
            F('proposta__projeto__nota'),
            descending=True,
            nulls_last=True,
        ),
        '-criado_em',
    )

    contexto = {
        'indicacoes': indicacoes,
        'pendentes': indicacoes.filter(status='pendente').count(),
        'pode_implementar': pode_gerir(perfil),
    }
    return render(request, 'bolsas/indicacoes.html', contexto)


@login_required
@never_cache
def indicacao_implementar(request, pk):
    """Implementa a bolsa a partir de uma indicação (somente técnico+).

    Formulário de bolsa pré-preenchido com o projeto da proposta, o aluno
    indicado, a modalidade do edital e as datas vigentes.
    """
    if not pode_gerir(perfil_de(request.user)):
        raise PermissionDenied

    indicacao = get_object_or_404(
        Indicacao.objects.select_related('proposta', 'proposta__edital', 'aluno'),
        pk=pk,
    )
    if indicacao.status == 'implementada':
        messages.error(request, 'Esta indicação já foi implementada.')
        return redirect('indicacoes_lista')

    proposta = indicacao.proposta
    edital = proposta.edital
    hoje = localdate()
    iniciais = {
        'aluno': indicacao.aluno,
        'projeto': proposta.projeto,
        'modalidade': edital.modalidade if edital else None,
        'data_inicio': hoje,
        'data_fim': (
            edital.data_fim if edital and edital.data_fim >= hoje else None
        ),
        'status': 'ativa',
    }

    if request.method == 'POST':
        form = BolsaForm(request.POST)
        if form.is_valid():
            bolsa = form.save()
            indicacao.bolsa = bolsa
            indicacao.status = 'implementada'
            indicacao.save()
            messages.success(
                request,
                f'Bolsa de {bolsa.aluno.nome} implementada com sucesso.',
            )
            return redirect('bolsa_detalhe', pk=bolsa.pk)
    else:
        form = BolsaForm(initial=iniciais)

    return render(request, 'bolsas/form.html', {
        'form': form,
        'titulo': f'Implementar bolsa — {indicacao.aluno.nome}',
        # Indicador de decisão: nota da avaliação por pares do projeto (§3.5)
        'projeto_indicador': proposta.projeto,
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
