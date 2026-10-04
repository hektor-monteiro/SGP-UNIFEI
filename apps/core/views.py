from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.projetos.models import Projeto, Pessoa
from apps.bolsas.models import Bolsa
from apps.comprovantes.models import Comprovante
from apps.editais.models import Edital, Avaliacao
from apps.relatorios.models import PlanoTrabalho, Relatorio

from .models import LogAuditoria, Perfil
from .permissions import perfil_required, pode_gerir


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
