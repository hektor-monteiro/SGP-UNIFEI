"""Views dos módulos de Planos de Trabalho e Relatórios.

Planos — regras de acesso:
- Lista/Detalhe: aluno vê apenas os próprios; docente/técnico: todos.
- Criação: aluno (própria bolsa sem plano), docente (bolsas dos projetos que
  coordena), técnico+ (qualquer bolsa).
- Edição: aluno só os próprios em rascunho/reprovado e sem mudar status;
  docente: planos dos projetos que coordena (com status); técnico+ sempre.

Relatórios — regras de acesso:
- Lista/Detalhe: aluno vê apenas os próprios; demais perfis, todos.
- Criação/edição: mesmo escopo dos planos (uma restrição extra: o conteúdo
  só é editável em rascunho/reprovado, exceto técnico+).
- Submissão (POST): dono, orientador ou técnico+ — rascunho/reprovado →
  submetido (limpa avaliação anterior, se houver).
- Avaliação: orientador (coordenador do projeto da bolsa) ou técnico+;
  nota 0–10 + observações; aprovação automática pela nota mínima.
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.bolsas.models import Bolsa
from apps.core.models import Perfil
from apps.core.permissions import perfil_de, pode_gerir

from .forms import AvaliacaoRelatorioForm, PlanoTrabalhoForm, RelatorioForm
from .models import PlanoTrabalho, Relatorio

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


# --------------------------------------------------------------------------
# Relatórios do aluno (parcial/final)
# --------------------------------------------------------------------------

# Nota mínima para aprovação automática do relatório.
# TODO: tornar configurável pelo técnico+ (hoje fixa; Edital.nota_minima
# também usa 6,00 como padrão).
NOTA_MINIMA_RELATORIO = Decimal('6.00')


def _relatorios_visiveis(user):
    """Relatórios visíveis: aluno vê apenas os próprios; demais, todos."""
    relatorios = Relatorio.objects.select_related(
        'aluno', 'bolsa', 'bolsa__modalidade',
    )
    perfil = perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        return relatorios.filter(aluno=perfil.pessoa) if perfil.pessoa else relatorios.none()
    return relatorios


def _orientador_de(user, relatorio) -> bool:
    """Docente coordenador do projeto da bolsa do relatório (orientador)."""
    perfil = perfil_de(user)
    return bool(
        perfil and perfil.pessoa
        and perfil.perfil == Perfil.PERFIL_DOCENTE
        and relatorio.bolsa.projeto.coordenador_id == perfil.pessoa.id
    )


def _pode_editar(user, relatorio) -> bool:
    """Edita técnico+ sempre; aluno próprio e orientador só em rascunho/reprovado.

    A restrição de status preserva a integridade do conteúdo após a submissão.
    """
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    if relatorio.status not in STATUS_EDITAVEIS_PELO_ALUNO:
        return False
    if perfil and perfil.pessoa:
        if perfil.perfil == Perfil.PERFIL_ALUNO:
            return relatorio.aluno_id == perfil.pessoa.id
        return _orientador_de(user, relatorio)
    return False


def _pode_submeter(user, relatorio) -> bool:
    """Submete: dono (aluno), orientador ou técnico+ — de rascunho/reprovado."""
    if relatorio.status not in STATUS_EDITAVEIS_PELO_ALUNO:
        return False
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    if perfil and perfil.pessoa:
        if perfil.perfil == Perfil.PERFIL_ALUNO:
            return relatorio.aluno_id == perfil.pessoa.id
        return _orientador_de(user, relatorio)
    return False


def _pode_avaliar(user, relatorio) -> bool:
    """Avalia: técnico+ (gerir) ou orientador do projeto da bolsa.

    TODO: considerar co-orientadores (MembroEquipe) na autorização.
    """
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    return _orientador_de(user, relatorio)


@login_required
@never_cache
def lista_relatorios(request):
    """Lista de relatórios com filtros por status, tipo e busca por título."""
    relatorios = _relatorios_visiveis(request.user)

    status = request.GET.get('status', '')
    tipo = request.GET.get('tipo', '')
    busca = request.GET.get('q', '')
    if status:
        relatorios = relatorios.filter(status=status)
    if tipo:
        relatorios = relatorios.filter(tipo=tipo)
    if busca:
        relatorios = relatorios.filter(titulo__icontains=busca)

    perfil = perfil_de(request.user)
    gerir = pode_gerir(perfil)
    if gerir:
        editaveis = set()
        avaliaveis = set(
            relatorios.filter(status='submetido').values_list('pk', flat=True)
        )
    elif perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        editaveis = set(
            relatorios.filter(status__in=STATUS_EDITAVEIS_PELO_ALUNO)
            .values_list('pk', flat=True)
        )
        avaliaveis = set()
    elif perfil and perfil.pessoa:
        editaveis = set(
            relatorios.filter(
                bolsa__projeto__coordenador=perfil.pessoa,
                status__in=STATUS_EDITAVEIS_PELO_ALUNO,
            ).values_list('pk', flat=True)
        )
        avaliaveis = set(
            relatorios.filter(
                status='submetido',
                bolsa__projeto__coordenador=perfil.pessoa,
            ).values_list('pk', flat=True)
        )
    else:
        editaveis = set()
        avaliaveis = set()

    contexto = {
        'relatorios': relatorios.order_by('-criado_em'),
        'filtros': {'status': status, 'tipo': tipo, 'q': busca},
        'status_choices': Relatorio._meta.get_field('status').choices,
        'tipo_choices': Relatorio._meta.get_field('tipo').choices,
        'pode_criar': _bolsas_para(request.user).exists(),
        'pode_gerir': gerir,
        'editaveis': editaveis,
        'avaliaveis': avaliaveis,
    }
    return render(request, 'relatorios/lista.html', contexto)


@login_required
@never_cache
def detalhe_relatorio(request, pk):
    """Detalhe do relatório com a avaliação (se concluída)."""
    relatorio = get_object_or_404(
        Relatorio.objects.select_related(
            'aluno', 'bolsa', 'bolsa__modalidade', 'bolsa__projeto',
            'avaliado_por',
        ),
        pk=pk,
    )

    perfil = perfil_de(request.user)
    # Aluno só vê os próprios relatórios
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa or relatorio.aluno_id != perfil.pessoa.id:
            raise PermissionDenied

    contexto = {
        'relatorio': relatorio,
        'pode_editar': _pode_editar(request.user, relatorio),
        'pode_submeter': _pode_submeter(request.user, relatorio),
        'pode_avaliar': (
            _pode_avaliar(request.user, relatorio)
            and relatorio.status == 'submetido'
        ),
        'nota_minima': NOTA_MINIMA_RELATORIO,
    }
    return render(request, 'relatorios/detalhe.html', contexto)


@login_required
@never_cache
def novo_relatorio(request):
    """Criação de relatório (aluno na própria bolsa, etc.)."""
    perfil_de(request.user)  # usuários sem perfil → 403
    bolsas = _bolsas_para(request.user)

    # Pré-seleciona a bolsa vinda de ?bolsa=<id> (link na página da bolsa)
    inicial = {}
    bolsa_id = request.GET.get('bolsa')
    if bolsa_id and bolsas.filter(pk=bolsa_id).exists():
        inicial['bolsa'] = bolsa_id

    if request.method == 'POST':
        form = RelatorioForm(request.POST, bolsas=bolsas)
        if form.is_valid():
            relatorio = form.save()
            messages.success(
                request,
                'Relatório criado como rascunho. Revise e submeta para avaliação.',
            )
            return redirect('relatorio_detalhe', pk=relatorio.pk)
    else:
        form = RelatorioForm(initial=inicial, bolsas=bolsas)

    return render(request, 'relatorios/form.html', {
        'form': form,
        'titulo': 'Novo relatório',
        'relatorio': None,
    })


@login_required
@never_cache
def editar_relatorio(request, pk):
    """Edição de relatório (status e avaliação não são campos do formulário)."""
    relatorio = get_object_or_404(Relatorio, pk=pk)
    if not _pode_editar(request.user, relatorio):
        raise PermissionDenied

    bolsas = _bolsas_para(request.user)

    if request.method == 'POST':
        form = RelatorioForm(request.POST, instance=relatorio, bolsas=bolsas)
        if form.is_valid():
            form.save()
            messages.success(request, 'Relatório atualizado com sucesso.')
            return redirect('relatorio_detalhe', pk=relatorio.pk)
    else:
        form = RelatorioForm(instance=relatorio, bolsas=bolsas)

    return render(request, 'relatorios/form.html', {
        'form': form,
        'titulo': f'Editar relatório: {relatorio.titulo}',
        'relatorio': relatorio,
    })


@login_required
@require_POST
def submeter_relatorio(request, pk):
    """Marca o relatório como submetido para avaliação (somente POST).

    Re-submissão após reprovação limpa a avaliação anterior.
    """
    relatorio = get_object_or_404(Relatorio, pk=pk)
    if not _pode_submeter(request.user, relatorio):
        raise PermissionDenied

    relatorio.status = 'submetido'
    relatorio.data_submissao = timezone.now()
    relatorio.nota = None
    relatorio.observacoes = ''
    relatorio.avaliado_por = None
    relatorio.data_avaliacao = None
    relatorio.save()
    messages.success(request, 'Relatório submetido para avaliação.')
    return redirect('relatorio_detalhe', pk=relatorio.pk)


@login_required
@never_cache
def avaliar_relatorio(request, pk):
    """Avaliação do relatório: nota 0–10 + observações.

    Aprovação automática: nota >= NOTA_MINIMA_RELATORIO → aprovado;
    abaixo → reprovado. Apenas relatórios em status 'submetido'.
    """
    relatorio = get_object_or_404(
        Relatorio.objects.select_related('aluno', 'bolsa', 'bolsa__modalidade'),
        pk=pk,
    )
    if not _pode_avaliar(request.user, relatorio):
        raise PermissionDenied
    if relatorio.status != 'submetido':
        messages.error(
            request,
            'Apenas relatórios submetidos podem ser avaliados '
            f'(status atual: {relatorio.get_status_display()}).',
        )
        return redirect('relatorio_detalhe', pk=relatorio.pk)

    if request.method == 'POST':
        form = AvaliacaoRelatorioForm(request.POST)
        if form.is_valid():
            nota = form.cleaned_data['nota']
            relatorio.nota = nota
            relatorio.observacoes = form.cleaned_data['observacoes']
            perfil = perfil_de(request.user)
            relatorio.avaliado_por = perfil.pessoa if perfil else None
            relatorio.data_avaliacao = timezone.now()
            relatorio.status = 'aprovado' if nota >= NOTA_MINIMA_RELATORIO else 'reprovado'
            relatorio.save()
            messages.success(
                request,
                f'Relatório avaliado: {relatorio.get_status_display()} (nota {nota}).',
            )
            return redirect('relatorio_detalhe', pk=relatorio.pk)
    else:
        form = AvaliacaoRelatorioForm()

    return render(request, 'relatorios/avaliar.html', {
        'form': form,
        'relatorio': relatorio,
        'nota_minima': NOTA_MINIMA_RELATORIO,
    })
