from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.projetos.models import Projeto, Pessoa
from apps.bolsas.models import Bolsa
from apps.comprovantes.models import Comprovante
from apps.editais.models import Edital, Avaliacao
from apps.relatorios.models import PlanoTrabalho, Relatorio

from .forms import SolicitacaoLGPDForm, TratarSolicitacaoForm
from .lgpd import anonimizar_titular, vinculos_ativos
from .middleware import _ip_da_requisicao
from .models import LogAuditoria, Perfil, SolicitacaoLGPD
from .permissions import perfil_de, perfil_required, pode_gerir


def index(request):
    """Página inicial (pública)."""
    if request.user.is_authenticated:
        return render(request, 'core/index.html')
    return render(request, 'core/index.html')


@login_required
@never_cache
def dashboard(request):
    """Painel do usuário autenticado com resumo de dados conforme seu perfil."""
    perfil = getattr(request.user, 'perfil', None)

    # Relatórios submetidos que o usuário pode avaliar:
    # técnico+ (ou superusuário): todos; docente: os de seus orientandos.
    relatorios_avaliar = Relatorio.objects.none()
    if request.user.is_superuser or (perfil and perfil.pelo_menos('tecnico')):
        relatorios_avaliar = Relatorio.objects.filter(status='submetido')
    elif perfil and perfil.perfil == 'docente' and perfil.pessoa:
        relatorios_avaliar = Relatorio.objects.filter(
            status='submetido',
            bolsa__projeto__coordenador=perfil.pessoa,
        )

    contexto = {
        'perfil': perfil,
        'e_superuser': request.user.is_superuser,
        # Avaliações de propostas alocadas para o usuário e ainda pendentes
        'avaliacoes_pendentes': (
            Avaliacao.objects.filter(
                avaliador=request.user,
                status='alocada',
                tipo='proposta',
            ).select_related('proposta__edital')
        ),
        'relatorios_avaliar': relatorios_avaliar.select_related(
            'aluno', 'bolsa__modalidade',
        ),
    }

    # Dados visíveis conforme nível hierárquico
    if request.user.is_superuser or (perfil and perfil.pelo_menos('tecnico')):
        contexto.update({
            'total_projetos': Projeto.objects.count(),
            'total_bolsas': Bolsa.objects.filter(status='ativa').count(),
            'total_editais': Edital.objects.count(),
            'total_pessoas': Pessoa.objects.count(),
            'mostrar_tudo': True,
        })
    elif perfil and perfil.perfil == 'docente':
        # Docente vê apenas seus projetos (vínculo via Perfil.pessoa;
        # NÃO filtrar por e-mail: o e-mail do usuário pode diferir do da Pessoa)
        meus_projetos = (
            Projeto.objects.filter(coordenador=perfil.pessoa)
            if perfil.pessoa
            else Projeto.objects.none()
        )
        contexto.update({
            'meus_projetos': meus_projetos,
            'total_projetos': meus_projetos.count(),
            'mostrar_meus_projetos': True,
        })
    else:
        # Aluno: vê seus planos, relatórios e comprovantes
        planos = (
            PlanoTrabalho.objects.filter(aluno=perfil.pessoa).select_related('bolsa__modalidade')
            if perfil and perfil.pessoa else PlanoTrabalho.objects.none()
        )
        relatorios = (
            Relatorio.objects.filter(aluno=perfil.pessoa).select_related('bolsa__modalidade')
            if perfil and perfil.pessoa else Relatorio.objects.none()
        )
        comprovantes = (
            Comprovante.objects.filter(
                Q(pessoa=perfil.pessoa) | Q(emitido_por=request.user),
            ).select_related('bolsa__modalidade', 'projeto')[:5]
            if perfil and perfil.pessoa else Comprovante.objects.none()
        )
        contexto.update({
            'mostrar_aluno': True,
            'meus_planos': planos,
            'meus_relatorios': relatorios,
            'meus_comprovantes': comprovantes,
        })

    return render(request, 'core/dashboard.html', contexto)


# ---------------------------------------------------------------------------
# LGPD (§6) — consentimento, direito de acesso e logs de auditoria
# ---------------------------------------------------------------------------

@login_required
@never_cache
def lgpd_pagina(request):
    """Página de privacidade: consentimento, direitos do titular e DPO (§6)."""
    perfil = getattr(request.user, 'perfil', None)
    contexto = {
        'perfil': perfil,
        'pode_ver_auditoria': pode_gerir(perfil),
    }
    return render(request, 'core/lgpd.html', contexto)


@login_required
def lgpd_consentimento(request):
    """Registra o consentimento explícito do titular para coleta de dados."""
    if request.method != 'POST':
        return redirect('lgpd')
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        # Superusuário não possui Perfil — consentimento não se aplica
        return redirect('lgpd')
    perfil.consentimento_lgpd = True
    perfil.data_consentimento = timezone.now()
    perfil.save(update_fields=[
        'consentimento_lgpd', 'data_consentimento', 'atualizado_em',
    ])
    messages.success(request, 'Consentimento registrado. Obrigado!')
    return redirect('lgpd')


@login_required
@never_cache
def lgpd_meus_dados(request):
    """Exportação dos próprios dados em JSON (direito de acesso — §6)."""
    perfil = getattr(request.user, 'perfil', None)
    pessoa = perfil.pessoa if perfil and perfil.pessoa_id else None

    dados = {
        'usuario': {
            'username': request.user.username,
            'email': request.user.email,
            'nome': request.user.get_full_name(),
            'data_criacao': request.user.date_joined,
            'ultimo_acesso': request.user.last_login,
            'perfil': {
                'perfil': perfil.perfil if perfil else None,
                'consentimento_lgpd': perfil.consentimento_lgpd if perfil else None,
                'data_consentimento': perfil.data_consentimento if perfil else None,
            },
        },
        'pessoa': None,
        'bolsas': [],
        'planos_de_trabalho': [],
        'relatorios': [],
        'comprovantes': [],
        'avaliacoes_de_propostas': [],
    }

    if pessoa:
        dados['pessoa'] = {
            'nome': pessoa.nome,
            'email': pessoa.email,
            'cpf': pessoa.cpf,
            'matricula': pessoa.matricula,
            'tipo': pessoa.tipo,
            'instituicao': pessoa.instituicao.sigla if pessoa.instituicao_id else None,
            'ativo': pessoa.ativo,
        }
        dados['bolsas'] = list(Bolsa.objects.filter(aluno=pessoa).values(
            'modalidade__sigla', 'status', 'data_inicio', 'data_fim',
            'valor_mensal', 'projeto__codigo',
        ))
        dados['planos_de_trabalho'] = list(PlanoTrabalho.objects.filter(
            aluno=pessoa,
        ).values(
            'titulo', 'status', 'data_submissao', 'data_aprovacao',
            'projeto__codigo',
        ))
        dados['relatorios'] = list(Relatorio.objects.filter(aluno=pessoa).values(
            'tipo', 'titulo', 'status', 'nota',
            'periodo_inicio', 'periodo_fim',
            'data_submissao', 'data_avaliacao',
        ))
        dados['comprovantes'] = list(Comprovante.objects.filter(
            Q(pessoa=pessoa) | Q(emitido_por=request.user),
        ).values(
            'tipo', 'descricao', 'codigo_verificacao', 'emitido_em',
        ))

    dados['avaliacoes_de_propostas'] = list(Avaliacao.objects.filter(
        avaliador=request.user,
    ).values(
        'tipo', 'status', 'nota', 'parecer',
        'proposta__titulo', 'data_avaliacao', 'data_conclusao',
    ))

    resposta = JsonResponse(
        dados,
        encoder=DjangoJSONEncoder,
        json_dumps_params={'ensure_ascii': False, 'indent': 2},
    )
    resposta['Content-Disposition'] = (
        'attachment; filename="meus-dados-lgpd.json"'
    )
    return resposta


@never_cache
@perfil_required(Perfil.PERFIL_TECNICO, Perfil.PERFIL_DIRETOR, Perfil.PERFIL_PROREITOR)
def auditoria(request):
    """Logs de auditoria (§6): quem acessou o quê e quando — técnicos+."""
    logs = LogAuditoria.objects.select_related('usuario')
    total = logs.count()

    acao = request.GET.get('acao', '')
    busca = request.GET.get('q', '')
    if acao:
        logs = logs.filter(acao=acao)
    if busca:
        logs = logs.filter(
            Q(usuario__username__icontains=busca)
            | Q(caminho__icontains=busca)
            | Q(ip__icontains=busca)
        )

    contexto = {
        'logs': logs[:200],
        'total': total,
        'acaoes': LogAuditoria.ACOES,
        'filtros': {'acao': acao, 'q': busca},
    }
    return render(request, 'core/auditoria.html', contexto)


# ---------------------------------------------------------------------------
# LGPD (§6) — solicitações de titular: correção e exclusão/anonimização
# ---------------------------------------------------------------------------

def _pode_tratar(perfil) -> bool:
    """Encarregado/DPO: superusuário, técnico, diretor e pro-reitor."""
    return pode_gerir(perfil)


@login_required
@never_cache
def solicitacoes_lista(request):
    """Solicitações do titular; técnicos+ (encarregado) veem todas."""
    perfil = perfil_de(request.user)
    gerente = _pode_tratar(perfil)

    solicitacoes = SolicitacaoLGPD.objects.select_related(
        'titular', 'tratado_por',
    )
    filtros = {'status': '', 'tipo': ''}
    if gerente:
        if request.GET.get('status'):
            filtros['status'] = request.GET['status']
            solicitacoes = solicitacoes.filter(status=filtros['status'])
        if request.GET.get('tipo'):
            filtros['tipo'] = request.GET['tipo']
            solicitacoes = solicitacoes.filter(tipo=filtros['tipo'])
    else:
        solicitacoes = solicitacoes.filter(titular=request.user)

    contexto = {
        'solicitacoes': solicitacoes,
        'gerente': gerente,
        'status_opcoes': SolicitacaoLGPD.STATUS,
        'tipo_opcoes': SolicitacaoLGPD.TIPOS,
        'filtros': filtros,
    }
    return render(request, 'core/solicitacoes.html', contexto)


@login_required
@never_cache
def solicitacao_nova(request):
    """Abre uma solicitação de correção ou exclusão (titular com perfil)."""
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        # Superusuário não é titular de dados pessoais no sistema.
        messages.info(
            request,
            'Usuário administrativo não possui dados de titular — '
            'a solicitação não se aplica.',
        )
        return redirect('lgpd_solicitacoes')

    if request.method == 'POST':
        form = SolicitacaoLGPDForm(request.POST, titular=request.user)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.titular = request.user
            solicitacao.save()
            messages.success(
                request,
                'Solicitação registrada. O encarregado irá analisá-la.',
            )
            return redirect('lgpd_solicitacao_detalhe', pk=solicitacao.pk)
    else:
        form = SolicitacaoLGPDForm(titular=request.user)

    return render(request, 'core/solicitacao_form.html', {
        'form': form,
        'titulo': 'Nova solicitação LGPD',
    })


@login_required
@never_cache
def solicitacao_detalhe(request, pk):
    """Detalhe da solicitação; quem não é titular só vê a própria (404)."""
    perfil = perfil_de(request.user)
    gerente = _pode_tratar(perfil)

    solicitacoes = SolicitacaoLGPD.objects.select_related(
        'titular', 'tratado_por',
    )
    if not gerente:
        solicitacoes = solicitacoes.filter(titular=request.user)
    solicitacao = get_object_or_404(solicitacoes, pk=pk)

    # Exclusão: mostra os vínculos que impedem a anonimização (auxilia o
    # encarregado a concluir ou indeferir).
    bloqueios = []
    pessoa = None
    if solicitacao.tipo == SolicitacaoLGPD.TIPO_EXCLUSAO:
        perfil_titular = getattr(solicitacao.titular, 'perfil', None)
        pessoa = (
            perfil_titular.pessoa
            if perfil_titular and perfil_titular.pessoa_id
            else None
        )
        if pessoa is not None:
            bloqueios = vinculos_ativos(pessoa)

    tratar_form = None
    if gerente and not solicitacao.esta_final:
        tratar_form = TratarSolicitacaoForm(instance=solicitacao)

    contexto = {
        'solicitacao': solicitacao,
        'gerente': gerente,
        'bloqueios': bloqueios,
        'tratar_form': tratar_form,
    }
    return render(request, 'core/solicitacao_detalhe.html', contexto)


@login_required
def solicitacao_tratar(request, pk):
    """Tratamento pelo encarregado: mover status ou concluir a exclusão.

    Concluir uma exclusão executa a anonimização dos dados pessoais —
    bloqueada enquanto houver vínculos ativos (aí deve ser indeferida).
    """
    if request.method != 'POST':
        return redirect('lgpd_solicitacoes')

    perfil = perfil_de(request.user)
    if not _pode_tratar(perfil):
        raise PermissionDenied

    solicitacao = get_object_or_404(SolicitacaoLGPD, pk=pk)
    if solicitacao.esta_final:
        messages.info(request, 'Esta solicitação já foi finalizada.')
        return redirect('lgpd_solicitacao_detalhe', pk=pk)

    form = TratarSolicitacaoForm(request.POST, instance=solicitacao)
    if not form.is_valid():
        for erro in form.non_field_errors():
            messages.error(request, erro)
        return redirect('lgpd_solicitacao_detalhe', pk=pk)

    solicitacao = form.save(commit=False)

    if (
        solicitacao.tipo == SolicitacaoLGPD.TIPO_EXCLUSAO
        and solicitacao.status == SolicitacaoLGPD.STATUS_CONCLUIDA
    ):
        perfil_titular = getattr(solicitacao.titular, 'perfil', None)
        pessoa = (
            perfil_titular.pessoa
            if perfil_titular and perfil_titular.pessoa_id
            else None
        )
        bloqueios = vinculos_ativos(pessoa) if pessoa else []
        if bloqueios:
            messages.error(
                request,
                'Não é possível concluir a exclusão: '
                + '; '.join(bloqueios)
                + '. Resolva os vínculos ou indefira a solicitação.',
            )
            return redirect('lgpd_solicitacao_detalhe', pk=pk)
        anonimizar_titular(solicitacao.titular)
        LogAuditoria.objects.create(
            usuario=request.user,
            acao='exclusao',
            caminho=request.path[:200],
            view='solicitacao_tratar',
            metodo='POST',
            status=200,
            ip=_ip_da_requisicao(request),
        )

    solicitacao.tratado_por = request.user
    solicitacao.tratado_em = timezone.now()
    solicitacao.save()
    messages.success(request, 'Solicitação atualizada.')
    return redirect('lgpd_solicitacao_detalhe', pk=solicitacao.pk)


@login_required
def lgpd_revogar_consentimento(request):
    """Revogação do consentimento (art. 8º, §5º da LGPD)."""
    if request.method != 'POST':
        return redirect('lgpd')
    perfil = getattr(request.user, 'perfil', None)
    if perfil is None:
        return redirect('lgpd')
    perfil.consentimento_lgpd = False
    perfil.data_consentimento = None
    perfil.save(update_fields=[
        'consentimento_lgpd', 'data_consentimento', 'atualizado_em',
    ])
    messages.success(
        request,
        'Consentimento revogado. Seus dados continuam apenas para '
        'cumprimento das finalidades do sistema.',
    )
    return redirect('lgpd')
