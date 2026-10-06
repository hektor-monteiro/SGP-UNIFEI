"""Views do módulo de Editais.

Fluxo de vida (requisito §3.1):
    rascunho → aprovado → em_andamento → encerrado
                 (qualquer status operacional pode ir para cancelado)

Permissões:
- Lista/Detalhe: todos os autenticados, mas abaixo de técnicos (aluno e
  docente) só aparecem/acesam editais com status 'em_andamento'.
- Criação/Edição: técnico, diretor, pro-reitor (o técnico cria).
- Aprovar/validar: SOMENTE diretor ou pro-reitor (requisito: "Técnico cria,
  Diretor/Pro-reitor valida") — carimba validado_por/data_validacao.
- Iniciar/Encerrar/Cancelar: técnico+.

Propostas (submissão a editais):
- Submissão: somente docente, a edital em andamento e no período —
  a proposta solicita cotas de bolsa para um projeto (§3.5). Aluno não
  submete: ele é indicado pelo docente após a aprovação das cotas.
- Detalhe/Edição: submetente ou técnico+; edição somente enquanto "submetida".
- Indicação de aluno: submetente ou téc+, só em proposta aprovada e
  enquanto houver cotas disponíveis; implementação da bolsa: só téc+.
- Listagem no edital: técnico+ vê todas; demais veem apenas as próprias.
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.utils.timezone import localdate, now

from apps.core.models import Perfil
from apps.core.permissions import perfil_de, pode_gerir
from apps.bolsas.forms import IndicacaoForm
from apps.bolsas.models import ModalidadeBolsa
from apps.projetos.models import Projeto, Proposta

from .forms import (
    AlocacaoForm,
    AvaliacaoForm,
    CriterioForm,
    EditalForm,
    PropostaForm,
)
from .models import Avaliacao, CriterioAvaliacao, Edital, NotaCriterio

# Ações do fluxo: origens permitidas, destino, nível mínimo e rótulo
ACOES = {
    'aprovar': {
        'origens': ('rascunho',),
        'destino': 'aprovado',
        'nivel': Perfil.PERFIL_DIRETOR,
        'rotulo': 'Aprovar e validar',
        'mensagem': 'aprovado e validado',
    },
    'iniciar': {
        'origens': ('aprovado',),
        'destino': 'em_andamento',
        'nivel': Perfil.PERFIL_TECNICO,
        'rotulo': 'Iniciar execução',
        'mensagem': 'em andamento',
    },
    'encerrar': {
        'origens': ('aprovado', 'em_andamento'),
        'destino': 'encerrado',
        'nivel': Perfil.PERFIL_TECNICO,
        'rotulo': 'Encerrar',
        'mensagem': 'encerrado',
    },
    'cancelar': {
        'origens': ('rascunho', 'aprovado', 'em_andamento'),
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


def _edital_aberto_para_submissao(edital) -> bool:
    """Edital aceita submissões: em andamento e dentro do período.

    Edital aprovado (validado, mas ainda não iniciado) não recebe
    propostas — é preciso estar em execução (requisito §3.1).
    """
    hoje = localdate()
    return (
        edital.status == 'em_andamento'
        and edital.data_inicio <= hoje <= edital.data_fim
    )


def _pode_submeter(perfil) -> bool:
    """Somente docente submete proposta (solicita cotas, requisito §3.5).

    Aluno não submete: ele é indicado pelo docente quando as cotas são
    aprovadas no edital. Técnicos+ gerenciam, não submetem.
    """
    return perfil is not None and perfil.perfil == Perfil.PERFIL_DOCENTE


def _projetos_do_docente(perfil):
    """Projetos em que o docente pode solicitar cotas.

    Coordena o projeto ou é membro da equipe; sem pessoa vinculada,
    nenhum projeto.
    """
    if perfil is None or perfil.pessoa_id is None:
        return Projeto.objects.none()
    return Projeto.objects.filter(
        Q(coordenador=perfil.pessoa) | Q(membros__pessoa=perfil.pessoa),
    ).distinct()


def _media_ponderada(notas) -> Decimal | None:
    """Média ponderada das notas. `notas` = [(nota, peso), ...]."""
    soma_pesos = sum((peso for _, peso in notas), Decimal('0'))
    if soma_pesos <= 0:
        return None
    total = sum((nota * peso for nota, peso in notas), Decimal('0'))
    return (total / soma_pesos).quantize(Decimal('0.01'))


def _recalcular_proposta(proposta) -> None:
    """Reprocessa status e nota final da proposta após mudanças nas avaliações.

    Regras:
    - Sem alocações: volta para 'submetida'.
    - Com avaliações concluídas: nota final = média simples das notas.
    - Todas as alocações concluídas: aprovação automática se a nota final
      for igual ou superior à nota mínima do edital (definida pelo técnico+).
    - Caso contrário: 'em_avaliacao'.
    """
    avaliacoes = list(proposta.avaliacoes.all())
    concluidas = [a for a in avaliacoes if a.status == 'concluida' and a.nota is not None]

    if not avaliacoes:
        proposta.status = 'submetida'
        proposta.nota_final = None
    elif not concluidas:
        proposta.status = 'em_avaliacao'
        proposta.nota_final = None
    else:
        media = sum((a.nota for a in concluidas), Decimal('0')) / len(concluidas)
        proposta.nota_final = media.quantize(Decimal('0.01'))
        if len(concluidas) == len(avaliacoes):
            minima = (
                proposta.edital.nota_minima
                if proposta.edital is not None
                else Decimal('6.00')
            )
            proposta.status = (
                'aprovada' if proposta.nota_final >= minima else 'reprovada'
            )
        else:
            proposta.status = 'em_avaliacao'
    proposta.save()


@login_required
@never_cache
def lista(request):
    """Lista de editais com filtros por status e modalidade.

    Abaixo de técnicos, só aparecem editais em execução ('em_andamento')
    e o filtro de status se resume a essa opção (requisito §3.1).
    """
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
    gerir = pode_gerir(perfil)
    todas = Edital._meta.get_field('status').choices
    if not gerir:
        editais = editais.filter(status='em_andamento')
        todas = tuple(c for c in todas if c[0] == 'em_andamento')
    contexto = {
        'editais': editais,
        'filtros': {'status': status, 'modalidade': modalidade, 'q': busca},
        'status_choices': todas,
        'modalidades': ModalidadeBolsa.objects.filter(ativo=True),
        'pode_gerir': gerir,
    }
    return render(request, 'editais/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe do edital com as ações do fluxo e as propostas submetidas.

    Abaixo de técnicos, só o edital 'em andamento' é acessível; os demais
    status são restritos à gestão (requisito §3.1).
    """
    edital = get_object_or_404(
        Edital.objects.select_related('modalidade', 'criado_por', 'validado_por'),
        pk=pk,
    )

    perfil = perfil_de(request.user)
    gerir = pode_gerir(perfil)
    if not gerir and edital.status != 'em_andamento':
        raise PermissionDenied

    acoes_disponiveis = [
        (acao, cfg['rotulo'])
        for acao, cfg in ACOES.items()
        if edital.status in cfg['origens'] and _pode_executar(request.user, acao)
    ]

    propostas = edital.propostas.select_related('submetido_por').order_by('-data_submissao')
    if not gerir:
        # Não-gerentes veem apenas as próprias propostas
        pessoa = perfil.pessoa if perfil is not None else None
        propostas = (
            propostas.filter(submetido_por=pessoa)
            if pessoa
            else edital.propostas.none()
        )

    contexto = {
        'edital': edital,
        'pode_gerir': gerir,
        'acoes_disponiveis': acoes_disponiveis,
        'propostas': propostas,
        'pode_submeter': _pode_submeter(perfil),
        'aceita_submissoes': _edital_aberto_para_submissao(edital),
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
    if acao == 'aprovar':
        edital.validado_por = request.user
        edital.data_validacao = now()
    edital.save()
    messages.success(request, f'Edital {edital.codigo}: {cfg["mensagem"]}.')
    return redirect('edital_detalhe', pk=edital.pk)


# --------------------------------------------------------------------------
# Propostas (submissão a editais)
# --------------------------------------------------------------------------

def _acesso_a_proposta(perfil, proposta) -> bool:
    """Gerente vê/edita qualquer proposta; demais, apenas a própria."""
    if pode_gerir(perfil):
        return True
    return perfil is not None and perfil.pessoa_id == proposta.submetido_por_id


def _pode_ver_proposta(user, perfil, proposta) -> bool:
    """Acesso de leitura: gerente, submetente ou avaliador alocado."""
    if _acesso_a_proposta(perfil, proposta):
        return True
    return proposta.avaliacoes.filter(avaliador=user).exists()


@login_required
@never_cache
def proposta_nova(request, pk):
    """Submissão de proposta a um edital aberto (aluno/docente)."""
    perfil = perfil_de(request.user)
    if not _pode_submeter(perfil):
        raise PermissionDenied

    edital = get_object_or_404(Edital, pk=pk)

    if not _edital_aberto_para_submissao(edital):
        messages.error(
            request,
            f'O edital {edital.codigo} não está aberto para submissões.',
        )
        # Redireciona para a lista: o detalhe pode ser oculto para o
        # submetente (abaixo de técnicos, editais fora de execução).
        return redirect('editais_lista')

    pessoa = perfil.pessoa
    if pessoa is None:
        messages.error(
            request,
            'Seu perfil não está vinculado a uma Pessoa. Procure o técnico da DIP.',
        )
        return redirect('edital_detalhe', pk=edital.pk)

    if request.method == 'POST':
        form = PropostaForm(request.POST, projetos=_projetos_do_docente(perfil))
        if form.is_valid():
            proposta = form.save(commit=False)
            proposta.edital = edital
            proposta.submetido_por = pessoa
            proposta.save()
            messages.success(request, 'Proposta submetida com sucesso.')
            return redirect('proposta_detalhe', pk=proposta.pk)
    else:
        form = PropostaForm(projetos=_projetos_do_docente(perfil))

    return render(request, 'editais/proposta_form.html', {
        'form': form,
        'edital': edital,
        'titulo': f'Submeter proposta — {edital.codigo}',
    })


@login_required
@never_cache
def proposta_detalhe(request, pk):
    """Detalhe da proposta: submetente, avaliador alocado ou técnico+."""
    proposta = get_object_or_404(
        Proposta.objects.select_related('edital', 'submetido_por', 'projeto'),
        pk=pk,
    )
    perfil = perfil_de(request.user)
    if not _pode_ver_proposta(request.user, perfil, proposta):
        raise PermissionDenied

    indicadas = proposta.indicacoes.count()
    cotas = proposta.cotas or 0
    disponiveis = max(cotas - indicadas, 0)
    sou_submetente = (
        perfil is not None and perfil.pessoa_id == proposta.submetido_por_id
    )

    contexto = {
        'proposta': proposta,
        'pode_editar': (
            proposta.status == 'submetida' and _acesso_a_proposta(perfil, proposta)
        ),
        'pode_gerir': pode_gerir(perfil),
        'cotas_indicadas': indicadas,
        'cotas_disponiveis': disponiveis,
        'pode_indicar': (
            proposta.status == 'aprovada'
            and disponiveis > 0
            and (pode_gerir(perfil) or sou_submetente)
        ),
        'pode_implementar': pode_gerir(perfil),
        'avaliacoes': proposta.avaliacoes.select_related(
            'avaliador', 'alocado_por',
        ).order_by('-data_avaliacao'),
    }
    return render(request, 'editais/proposta_detalhe.html', contexto)


@login_required
@never_cache
def proposta_editar(request, pk):
    """Edição da proposta: submetente ou técnico+, só enquanto "submetida"."""
    proposta = get_object_or_404(Proposta, pk=pk)
    perfil = perfil_de(request.user)
    if not _acesso_a_proposta(perfil, proposta):
        raise PermissionDenied

    if proposta.status != 'submetida':
        messages.error(
            request,
            'Propostas em avaliação não podem ser editadas.',
        )
        return redirect('proposta_detalhe', pk=proposta.pk)

    if request.method == 'POST':
        form = PropostaForm(
            request.POST, instance=proposta, projetos=_projetos_ou_todos(perfil),
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Proposta atualizada com sucesso.')
            return redirect('proposta_detalhe', pk=proposta.pk)
    else:
        form = PropostaForm(instance=proposta, projetos=_projetos_ou_todos(perfil))

    return render(request, 'editais/proposta_form.html', {
        'form': form,
        'edital': proposta.edital,
        'titulo': 'Editar proposta',
    })


def _projetos_ou_todos(perfil):
    """Téc+ escolhem qualquer projeto; docente, só os seus."""
    if pode_gerir(perfil):
        return None
    return _projetos_do_docente(perfil)


@login_required
@never_cache
def proposta_indicar(request, pk):
    """Indica aluno para cota de proposta aprovada (submetente ou téc+).

    Regras (§3.5): só proposta com status 'aprovada' e enquanto houver
    cotas disponíveis (indicadas < solicitadas). O técnico implementa a
    bolsa depois, a partir da indicação.
    """
    proposta = get_object_or_404(
        Proposta.objects.select_related('edital', 'submetido_por'),
        pk=pk,
    )
    perfil = perfil_de(request.user)
    sou_submetente = (
        perfil is not None and perfil.pessoa_id == proposta.submetido_por_id
    )
    if not (pode_gerir(perfil) or sou_submetente):
        raise PermissionDenied

    if proposta.status != 'aprovada':
        messages.error(
            request,
            'Só é possível indicar alunos após a aprovação das cotas no edital.',
        )
        return redirect('proposta_detalhe', pk=proposta.pk)

    indicadas = proposta.indicacoes.count()
    if indicadas >= proposta.cotas:
        messages.error(
            request,
            f'Todas as {proposta.cotas} cotas da proposta já foram indicadas.',
        )
        return redirect('proposta_detalhe', pk=proposta.pk)

    if request.method == 'POST':
        form = IndicacaoForm(request.POST, proposta=proposta)
        if form.is_valid():
            indicacao = form.save(commit=False)
            indicacao.proposta = proposta
            indicacao.indicado_por = (
                perfil.pessoa if (perfil and perfil.pessoa_id) else None
            )
            indicacao.save()
            messages.success(
                request,
                f'Aluno {indicacao.aluno.nome} indicado para a cota. '
                'O técnico irá implementar a bolsa.',
            )
            return redirect('proposta_detalhe', pk=proposta.pk)
    else:
        form = IndicacaoForm(proposta=proposta)

    return render(request, 'bolsas/indicar.html', {
        'form': form,
        'proposta': proposta,
        'disponiveis': proposta.cotas - indicadas,
        'titulo': f'Indicar aluno — {proposta.titulo[:60]}',
    })


# --------------------------------------------------------------------------
# Critérios de avaliação (criação/edição por técnico+)
# --------------------------------------------------------------------------

@login_required
@never_cache
def criterios_lista(request):
    """Lista de critérios de avaliação (visível a todos; gestão por técnico+)."""
    contexto = {
        'criterios': CriterioAvaliacao.objects.all(),
        'pode_gerir': pode_gerir(perfil_de(request.user)),
    }
    return render(request, 'editais/criterios_lista.html', contexto)


@login_required
@never_cache
def criterio_novo(request):
    """Criação de critério de avaliação com peso (técnico+)."""
    if not pode_gerir(perfil_de(request.user)):
        raise PermissionDenied

    if request.method == 'POST':
        form = CriterioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Critério criado com sucesso.')
            return redirect('criterios_lista')
    else:
        form = CriterioForm()

    return render(request, 'editais/criterios_form.html', {
        'form': form,
        'titulo': 'Novo critério de avaliação',
    })


@login_required
@never_cache
def criterio_editar(request, pk):
    """Edição de critério de avaliação (técnico+)."""
    if not pode_gerir(perfil_de(request.user)):
        raise PermissionDenied

    criterio = get_object_or_404(CriterioAvaliacao, pk=pk)

    if request.method == 'POST':
        form = CriterioForm(request.POST, instance=criterio)
        if form.is_valid():
            form.save()
            messages.success(request, 'Critério atualizado com sucesso.')
            return redirect('criterios_lista')
    else:
        form = CriterioForm(instance=criterio)

    return render(request, 'editais/criterios_form.html', {
        'form': form,
        'titulo': f'Editar critério {criterio.nome}',
    })


# --------------------------------------------------------------------------
# Alocação e realização de avaliações
# --------------------------------------------------------------------------

@login_required
@never_cache
def proposta_alocar(request, pk):
    """Aloca docente avaliador à proposta (somente técnico+).

    Permte múltiplos avaliadores (banca); a realocação é feita removendo
    a alocação inadequada e alocando outro docente.
    """
    if not pode_gerir(perfil_de(request.user)):
        raise PermissionDenied

    proposta = get_object_or_404(Proposta.objects.select_related('edital'), pk=pk)

    if request.method == 'POST':
        form = AlocacaoForm(request.POST)
        if form.is_valid():
            avaliador = form.cleaned_data['avaliador']
            if Avaliacao.objects.filter(
                proposta=proposta, avaliador=avaliador,
            ).exists():
                form.add_error(
                    'avaliador',
                    'Este docente já está alocado para esta proposta.',
                )
            else:
                Avaliacao.objects.create(
                    tipo='proposta',
                    proposta=proposta,
                    avaliador=avaliador,
                    alocado_por=request.user,
                    status='alocada',
                )
                _recalcular_proposta(proposta)
                messages.success(
                    request,
                    f'Avaliação alocada para {avaliador.get_full_name() or avaliador.username}.',
                )
                return redirect('proposta_detalhe', pk=proposta.pk)
    else:
        form = AlocacaoForm()

    return render(request, 'editais/alocar.html', {
        'form': form,
        'proposta': proposta,
    })


@login_required
@never_cache
def avaliacao_detalhe(request, pk):
    """Formulário de avaliação de proposta (o próprio avaliador preenche).

    Notas de 0 a 10 por critério ativo + parecer; a nota final é a média
    ponderada pelos pesos dos critérios. Gerentes apenas visualizam.
    """
    avaliacao = get_object_or_404(
        Avaliacao.objects.select_related('proposta__edital', 'avaliador'),
        pk=pk,
        tipo='proposta',
    )
    perfil = perfil_de(request.user)
    sou_avaliador = avaliacao.avaliador_id == request.user.id
    if not sou_avaliador and not pode_gerir(perfil):
        raise PermissionDenied

    criterios = list(CriterioAvaliacao.objects.filter(ativo=True))
    notas_existentes = {
        n.criterio_id: n.nota for n in avaliacao.notas.select_related('criterio')
    }

    if request.method == 'POST':
        if not sou_avaliador:
            raise PermissionDenied
        if not criterios:
            messages.error(
                request,
                'Não há critérios de avaliação ativos. Procure o técnico da DIP.',
            )
            return redirect('avaliacao_detalhe', pk=avaliacao.pk)

        form = AvaliacaoForm(request.POST, criterios=criterios)
        if form.is_valid():
            for criterio in criterios:
                NotaCriterio.objects.update_or_create(
                    avaliacao=avaliacao,
                    criterio=criterio,
                    defaults={
                        'nota': form.cleaned_data[f'nota_{criterio.pk}'],
                    },
                )
            notas = [
                (n.nota, n.criterio.peso)
                for n in avaliacao.notas.select_related('criterio')
            ]
            media = _media_ponderada(notas)
            if media is None:
                messages.error(
                    request,
                    'Não foi possível calcular a nota final: '
                    'verifique os pesos dos critérios.',
                )
                return redirect('avaliacao_detalhe', pk=avaliacao.pk)

            avaliacao.parecer = form.cleaned_data['parecer']
            avaliacao.nota = media
            avaliacao.status = 'concluida'
            avaliacao.data_conclusao = now()
            avaliacao.save()
            _recalcular_proposta(avaliacao.proposta)
            messages.success(
                request,
                f'Avaliação concluída. Nota final (média ponderada): {media}.',
            )
            return redirect('avaliacao_detalhe', pk=avaliacao.pk)
    else:
        iniciais = {'parecer': avaliacao.parecer}
        for criterio in criterios:
            if criterio.pk in notas_existentes:
                iniciais[f'nota_{criterio.pk}'] = notas_existentes[criterio.pk]
        form = AvaliacaoForm(initial=iniciais, criterios=criterios)

    contexto = {
        'avaliacao': avaliacao,
        'proposta': avaliacao.proposta,
        'form': form,
        'criterios': criterios,
        'notas_existentes': notas_existentes,
        'linhas_notas': [
            {'criterio': n.criterio, 'nota': n.nota}
            for n in avaliacao.notas.select_related('criterio')
        ],
        'sou_avaliador': sou_avaliador,
        'pode_gerir': pode_gerir(perfil),
    }
    return render(request, 'editais/avaliacao.html', contexto)


@login_required
@require_POST
def avaliacao_remover(request, pk):
    """Remove alocação de avaliação para realocação (somente técnico+)."""
    if not pode_gerir(perfil_de(request.user)):
        raise PermissionDenied

    avaliacao = get_object_or_404(Avaliacao, pk=pk, tipo='proposta')
    proposta = avaliacao.proposta
    avaliacao.delete()
    _recalcular_proposta(proposta)
    messages.success(
        request,
        'Alocação removida. Um novo avaliador pode ser alocado.',
    )
    return redirect('proposta_detalhe', pk=proposta.pk)
