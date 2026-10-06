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
import csv
import io
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncYear
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.bolsas.models import Bolsa
from apps.core.arquivos import servir_pdf
from apps.core.models import Perfil
from apps.core.permissions import perfil_de, perfil_required, pode_gerir
from apps.editais.models import Edital
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Projeto, Proposta

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


def _pode_ver_plano(user, plano) -> None:
    """Levanta PermissionDenied se o usuário não pode ver o plano.

    Aluno só vê os próprios planos (LGPD); demais perfis veem todos.
    Usada pelo detalhe e pela entrega do PDF do plano.
    """
    perfil = perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa or plano.aluno_id != perfil.pessoa.id:
            raise PermissionDenied


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
        # Busca por título ou resumo (resumo é o texto curto da busca)
        planos = planos.filter(
            Q(titulo__icontains=busca) | Q(resumo__icontains=busca)
        )

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

    # Aluno só vê os próprios planos
    _pode_ver_plano(request.user, plano)

    contexto = {
        'plano': plano,
        'pode_editar': _pode_editar(request.user, plano),
        'muda_status': _muda_status(request.user, plano),
    }
    return render(request, 'planos/detalhe.html', contexto)


@login_required
@never_cache
def arquivo_plano(request, pk):
    """Entrega o PDF do plano de trabalho com a permissão do detalhe."""
    plano = get_object_or_404(PlanoTrabalho, pk=pk)
    _pode_ver_plano(request.user, plano)
    if not plano.arquivo_pdf:
        raise Http404('Este plano de trabalho não tem documento anexado.')
    return servir_pdf(plano.arquivo_pdf.path)


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
            request.POST, request.FILES, bolsas=bolsas, pode_mudar_status=pode_mudar,
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
            request.POST, request.FILES, instance=plano,
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


def _e_coorientador(user, relatorio) -> bool:
    """Docente com vínculo ativo de coorientador no projeto da bolsa."""
    perfil = perfil_de(user)
    if not (perfil and perfil.pessoa):
        return False
    if perfil.perfil != Perfil.PERFIL_DOCENTE:
        return False
    return MembroEquipe.objects.filter(
        projeto=relatorio.bolsa.projeto,
        pessoa=perfil.pessoa,
        funcao='coorientador',
        ativo=True,
    ).exists()


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


def _pode_ver_relatorio(user, relatorio) -> None:
    """Levanta PermissionDenied se o usuário não pode ver o relatório.

    Aluno só vê os próprios relatórios (LGPD); demais perfis (orientador,
    técnico+, etc.) veem todos. Usada pelo detalhe, pela avaliação e pela
    entrega do PDF.
    """
    perfil = perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa or relatorio.aluno_id != perfil.pessoa.id:
            raise PermissionDenied


def _pode_avaliar(user, relatorio) -> bool:
    """Avalia: técnico+ (gerir), orientador ou co-orientador ativo do projeto."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return True
    return _orientador_de(user, relatorio) or _e_coorientador(user, relatorio)


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
        # Busca por título ou resumo (resumo é o texto curto da busca)
        relatorios = relatorios.filter(
            Q(titulo__icontains=busca) | Q(resumo__icontains=busca)
        )

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
            relatorios.filter(status='submetido')
            .filter(
                Q(bolsa__projeto__coordenador=perfil.pessoa)
                | Q(
                    bolsa__projeto__membros__pessoa=perfil.pessoa,
                    bolsa__projeto__membros__funcao='coorientador',
                    bolsa__projeto__membros__ativo=True,
                )
            )
            .distinct()
            .values_list('pk', flat=True)
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

    # Aluno só vê os próprios relatórios
    _pode_ver_relatorio(request.user, relatorio)

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
def arquivo_relatorio(request, pk):
    """Entrega o PDF do relatório com a permissão do detalhe."""
    relatorio = get_object_or_404(Relatorio, pk=pk)
    _pode_ver_relatorio(request.user, relatorio)
    if not relatorio.arquivo_pdf:
        raise Http404('Este relatório não tem documento anexado.')
    return servir_pdf(relatorio.arquivo_pdf.path)


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
        form = RelatorioForm(request.POST, request.FILES, bolsas=bolsas)
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
        form = RelatorioForm(
            request.POST, request.FILES, instance=relatorio, bolsas=bolsas,
        )
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
    # Documento em PDF obrigatório para a submissão: é ele que o
    # avaliador leu; o resumo fica no sistema para a busca.
    if not relatorio.arquivo_pdf:
        messages.error(
            request,
            'Anexe o PDF do relatório (campo "Documento (PDF)") antes de '
            'submeter para avaliação.',
        )
        return redirect('relatorio_detalhe', pk=relatorio.pk)

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


def _barras(itens):
    """Anexa percentual relativo ao maior total (barras CSS no template)."""
    itens = list(itens)
    maior = max((item['total'] for item in itens), default=0)
    for item in itens:
        item['barra'] = round(item['total'] * 100 / maior) if maior else 0
    return itens


def _dados_indicadores() -> dict:
    """Agregações dos indicadores §5 — usadas no painel HTML e na exportação CSV."""
    # --- §5.1 Governamentais e de agências de fomento ---
    bolsas_modalidade = list(
        Bolsa.objects.values('modalidade__sigla')
        .annotate(total=Count('id'), ativas=Count('id', filter=Q(status='ativa')))
        .order_by('-total')
    )
    bolsas_fomentador = list(
        Bolsa.objects.values('fomentador__sigla')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    total_projetos = Projeto.objects.count()
    projetos_concluidos = Projeto.objects.filter(status='concluido').count()
    taxa_conclusao = (
        round(projetos_concluidos * 100 / total_projetos, 1) if total_projetos else 0.0
    )
    alunos_concluiram = (
        Bolsa.objects.filter(status='encerrada').values('aluno').distinct().count()
    )
    externos_total = MembroEquipe.objects.filter(funcao='externo').count()
    externos_ativos = MembroEquipe.objects.filter(funcao='externo', ativo=True).count()
    recursos_internos = (
        Projeto.objects.aggregate(t=Sum('recursos_internos'))['t'] or Decimal('0')
    )
    recursos_externos = (
        Projeto.objects.aggregate(t=Sum('recursos_externos'))['t'] or Decimal('0')
    )

    # --- §5.2 Indicadores de efetividade ---
    evolucao_bolsas = _barras(
        Bolsa.objects.filter(data_inicio__isnull=False)
        .annotate(ano=TruncYear('data_inicio'))
        .values('ano')
        .annotate(total=Count('id'))
        .order_by('ano')
    )
    evolucao_projetos = _barras(
        Projeto.objects.filter(data_inicio__isnull=False)
        .annotate(ano=TruncYear('data_inicio'))
        .values('ano')
        .annotate(total=Count('id'))
        .order_by('ano')
    )

    total_propostas = Proposta.objects.count()
    propostas_aprovadas = Proposta.objects.filter(status='aprovada').count()
    taxa_sucesso_editais = (
        round(propostas_aprovadas * 100 / total_propostas, 1) if total_propostas else 0.0
    )
    editais_taxas = []
    for edital in (
        Edital.objects.annotate(
            total_propostas=Count('propostas'),
            aprovadas=Count('propostas', filter=Q(propostas__status='aprovada')),
        )
        .filter(total_propostas__gt=0)
        .order_by('-data_inicio')
    ):
        editais_taxas.append({
            'codigo': edital.codigo,
            'titulo': edital.titulo,
            'total': edital.total_propostas,
            'aprovadas': edital.aprovadas,
            'taxa': round(edital.aprovadas * 100 / edital.total_propostas, 1),
        })

    duracoes = [
        (fim - inicio).days
        for inicio, fim in Projeto.objects.filter(
            status='concluido',
            data_inicio__isnull=False,
            data_termino__isnull=False,
        ).values_list('data_inicio', 'data_termino')
    ]
    tempo_medio_dias = round(sum(duracoes) / len(duracoes)) if duracoes else None

    orientandos = list(
        Bolsa.objects.filter(status='ativa')
        .values('projeto__coordenador__nome')
        .annotate(orientandos=Count('id'))
        .order_by('-orientandos')[:10]
    )

    alunos_com_bolsa = Bolsa.objects.values('aluno').distinct().count()
    alunos_renovaram = (
        Bolsa.objects.values('aluno').annotate(n=Count('id')).filter(n__gte=2).count()
    )
    taxa_renovacao = (
        round(alunos_renovaram * 100 / alunos_com_bolsa, 1) if alunos_com_bolsa else 0.0
    )

    contexto = {
        # KPIs do topo
        'total_projetos': total_projetos,
        'total_bolsas_ativas': Bolsa.objects.filter(status='ativa').count(),
        'total_editais': Edital.objects.count(),
        'taxa_conclusao': taxa_conclusao,
        # §5.1
        'bolsas_modalidade': bolsas_modalidade,
        'bolsas_fomentador': bolsas_fomentador,
        'projetos_concluidos': projetos_concluidos,
        'alunos_concluiram': alunos_concluiram,
        'externos_total': externos_total,
        'externos_ativos': externos_ativos,
        'recursos_internos': recursos_internos,
        'recursos_externos': recursos_externos,
        # §5.2
        'evolucao_bolsas': evolucao_bolsas,
        'evolucao_projetos': evolucao_projetos,
        'taxa_sucesso_editais': taxa_sucesso_editais,
        'total_propostas': total_propostas,
        'propostas_aprovadas': propostas_aprovadas,
        'editais_taxas': editais_taxas,
        'tempo_medio_dias': tempo_medio_dias,
        'orientandos': orientandos,
        'taxa_renovacao': taxa_renovacao,
        'alunos_com_bolsa': alunos_com_bolsa,
        'alunos_renovaram': alunos_renovaram,
    }
    return contexto


@never_cache
@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
def indicadores(request):
    """Painel de indicadores governamentais e de efetividade (§5).

    Indicadores sem fonte de dados no modelo atual ficam marcados com TODO
    na tela, em vez de exibir estimativas incorretas.
    """
    return render(request, 'relatorios/indicadores.html', _dados_indicadores())


def _num_csv(valor):
    """Número em formato pt-BR (vírgula decimal) para o CSV."""
    if isinstance(valor, Decimal):
        return format(valor, 'f').replace('.', ',')
    if isinstance(valor, float):
        return str(valor).replace('.', ',')
    return valor


def _escrever_indicadores_csv(writer, dados, usuario):
    """Escreve as seções dos indicadores (§5) em writer CSV com delimitador `;`."""
    writer.writerow(['SGP-UNIFEI — Indicadores de pesquisa'])
    writer.writerow(['Emitido em', timezone.localtime().strftime('%d/%m/%Y %H:%M')])
    writer.writerow(['Emitido por', usuario])
    writer.writerow([])

    # --- Visão geral (KPIs do topo) ---
    writer.writerow(['Visão geral'])
    writer.writerow(['Indicador', 'Valor'])
    writer.writerow(['Projetos', dados['total_projetos']])
    writer.writerow(['Bolsas ativas', dados['total_bolsas_ativas']])
    writer.writerow(['Editais', dados['total_editais']])
    writer.writerow([
        'Taxa de conclusão de projetos (%)',
        _num_csv(dados['taxa_conclusao']),
    ])
    writer.writerow([])

    # --- §5.1 ---
    writer.writerow(['5.1 Governamentais e de agências de fomento'])
    writer.writerow(['Bolsas por modalidade'])
    writer.writerow(['Modalidade', 'Total', 'Ativas'])
    for m in dados['bolsas_modalidade']:
        writer.writerow([
            m['modalidade__sigla'] or 'Não informado', m['total'], m['ativas'],
        ])
    writer.writerow([])

    writer.writerow(['Bolsas por fomentador'])
    writer.writerow(['Fomentador', 'Total'])
    for f in dados['bolsas_fomentador']:
        writer.writerow([f['fomentador__sigla'] or 'Não informado', f['total']])
    writer.writerow([])

    writer.writerow(['Projetos e recursos'])
    writer.writerow(['Indicador', 'Valor'])
    writer.writerow([
        'Projetos concluídos',
        f"{dados['projetos_concluidos']}/{dados['total_projetos']}",
    ])
    writer.writerow(['Alunos que concluíram a bolsa', dados['alunos_concluiram']])
    writer.writerow([
        'Membros externos (ativos/total)',
        f"{dados['externos_ativos']}/{dados['externos_total']}",
    ])
    writer.writerow([
        'Recursos internos vinculados (R$)',
        _num_csv(dados['recursos_internos']),
    ])
    writer.writerow([
        'Recursos externos vinculados (R$)',
        _num_csv(dados['recursos_externos']),
    ])
    writer.writerow([])

    # --- §5.2 ---
    writer.writerow(['5.2 Indicadores de efetividade'])
    writer.writerow(['Evolução — bolsas iniciadas por ano'])
    writer.writerow(['Ano', 'Bolsas'])
    for b in dados['evolucao_bolsas']:
        writer.writerow([b['ano'].year, b['total']])
    writer.writerow([])

    writer.writerow(['Evolução — projetos iniciados por ano'])
    writer.writerow(['Ano', 'Projetos'])
    for p in dados['evolucao_projetos']:
        writer.writerow([p['ano'].year, p['total']])
    writer.writerow([])

    writer.writerow(['Taxa de sucesso em editais'])
    writer.writerow(['Indicador', 'Valor'])
    writer.writerow([
        'Propostas aprovadas',
        f"{dados['propostas_aprovadas']}/{dados['total_propostas']}",
    ])
    writer.writerow(['Taxa geral (%)', _num_csv(dados['taxa_sucesso_editais'])])
    writer.writerow([])

    writer.writerow(['Sucesso por edital'])
    writer.writerow(['Edital', 'Título', 'Propostas', 'Aprovadas', 'Taxa (%)'])
    for e in dados['editais_taxas']:
        writer.writerow([
            e['codigo'], e['titulo'], e['total'], e['aprovadas'],
            _num_csv(e['taxa']),
        ])
    writer.writerow([])

    writer.writerow(['Orientados por docente (bolsas ativas)'])
    writer.writerow(['Docente', 'Orientandos'])
    for o in dados['orientandos']:
        writer.writerow([
            o['projeto__coordenador__nome'] or 'Não informado',
            o['orientandos'],
        ])
    writer.writerow([])

    writer.writerow(['Efetividade'])
    writer.writerow(['Indicador', 'Valor'])
    tempo = dados['tempo_medio_dias']
    writer.writerow([
        'Tempo médio de conclusão (dias)',
        tempo if tempo is not None else 'Sem dados',
    ])
    writer.writerow([
        'Alunos com 2 ou mais bolsas (%)',
        _num_csv(dados['taxa_renovacao']),
        f"{dados['alunos_renovaram']}/{dados['alunos_com_bolsa']}",
    ])


@never_cache
@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
def indicadores_csv(request):
    """Exportação CSV dos indicadores (§5) para prestação de contas.

    Delimitador `;` e vírgula decimal ( convenção Excel pt-BR), UTF-8 com BOM
    para os acentos abrirem corretamente.
    """
    dados = _dados_indicadores()

    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
    _escrever_indicadores_csv(writer, dados, request.user.get_username())

    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = (
        f'attachment; filename="indicadores-{timezone.localdate():%Y%m%d}.csv"'
    )
    resposta.write('\ufeff' + buffer.getvalue())
    return resposta
