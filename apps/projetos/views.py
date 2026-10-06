"""Views do módulo de Projetos.

Regras de acesso:
- Lista/Detalhe: todos os autenticados; alunos veem apenas seus projetos.
- Criação: docente (vira coordenador), técnico, diretor, pro-reitor.
- Edição: coordenador do projeto, técnico, diretor, pro-reitor.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.core.arquivos import servir_pdf
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


def _pode_ver(user, projeto) -> None:
    """Levanta PermissionDenied se o usuário não pode ver o projeto.

    Aluno só vê projetos dos quais participa (membro ou bolsista);
    demais perfis veem qualquer projeto. Usada pelo detalhe e pela
    entrega do PDF — o arquivo obedece à mesma regra da tela.
    """
    perfil = _perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if not perfil.pessoa:
            raise PermissionDenied
        participa = (
            projeto.membros.filter(pessoa=perfil.pessoa).exists()
            or projeto.bolsas.filter(aluno=perfil.pessoa).exists()
        )
        if not participa:
            raise PermissionDenied


def _visiveis_para(user):
    """Projetos visíveis: aluno vê os que é membro OU em que tem bolsa."""
    projetos = Projeto.objects.select_related(
        'coordenador', 'instituicao', 'fomentador',
    )
    perfil = _perfil_de(user)
    if perfil and perfil.perfil == Perfil.PERFIL_ALUNO:
        if perfil.pessoa:
            return projetos.filter(
                Q(membros__pessoa=perfil.pessoa) | Q(bolsas__aluno=perfil.pessoa)
            ).distinct()
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
        # Busca por código, título ou resumo (resumo é o texto curto
        # que alimenta a busca do sistema)
        projetos = projetos.filter(
            Q(codigo__icontains=busca)
            | Q(titulo__icontains=busca)
            | Q(resumo__icontains=busca)
        )

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
    # Aluno só vê projetos dos quais participa: como membro ou com bolsa nele
    _pode_ver(request.user, projeto)

    contexto = {
        'projeto': projeto,
        'membros': projeto.membros.select_related('pessoa').order_by('funcao'),
        'bolsas': projeto.bolsas.select_related(
            'aluno', 'modalidade', 'fomentador', 'plano_trabalho',
        ).all(),
        'pode_editar': _pode_editar(request.user, projeto),
        # Avaliação por pares (§3.4): alocações, status e nota
        'avaliacoes': projeto.avaliacoes.select_related(
            'avaliador', 'alocado_por',
        ).order_by('data_avaliacao'),
        'pode_submeter': (
            _pode_editar(request.user, projeto)
            and projeto.status_avaliacao == 'nao_submetido'
        ),
        'pode_alocar': (
            _pode_gerir(perfil)
            and projeto.status_avaliacao != 'nao_submetido'
            # Financiamento externo: nota 10,00 automática, sem banca
            and not projeto.nota_automatica
        ),
        # Docente (qualquer) e perfis técnicos+ veem os planos das bolsas;
        # aluno não vê planos de terceiros
        'mostrar_planos': perfil is None or perfil.perfil != Perfil.PERFIL_ALUNO,
    }
    return render(request, 'projetos/detalhe.html', contexto)


@login_required
@never_cache
def arquivo(request, pk):
    """Entrega o PDF do projeto com as mesmas permissões do detalhe.

    Nunca servimos /media publicamente: o arquivo obedece à visibilidade
    do projeto (aluno participante) e é emitido como application/pdf.
    """
    projeto = get_object_or_404(Projeto, pk=pk)
    _pode_ver(request.user, projeto)
    if not projeto.arquivo_pdf:
        raise Http404('Este projeto não tem documento anexado.')
    return servir_pdf(projeto.arquivo_pdf.path)


@login_required
@require_POST
def submeter(request, pk):
    """Envia o projeto para avaliação por pares (§3.4).

    Somente o coordenador (ou técnico+) dispara o envio; a partir daí o
    técnico aloca os avaliadores docentes e a nota resultante passa a
    ser exibida como indicador na alocação de bolsas. Projetos com
    financiamento externo já nascem avaliados com nota 10,00 (nota
    automática) e não precisam deste envio.
    """
    projeto = get_object_or_404(Projeto, pk=pk)
    if not _pode_editar(request.user, projeto):
        raise PermissionDenied
    if projeto.nota_automatica:
        messages.success(
            request,
            'Projeto com financiamento externo: nota 10,00 atribuída '
            'automaticamente — a avaliação por pares é dispensada.',
        )
        return redirect('projeto_detalhe', pk=projeto.pk)
    if projeto.status_avaliacao != 'nao_submetido':
        messages.error(
            request,
            'Este projeto já foi enviado para avaliação por pares.',
        )
        return redirect('projeto_detalhe', pk=projeto.pk)
    # Documento em PDF obrigatório para a submissão (§3.1): é ele que os
    # avaliadores leem; o resumo fica no sistema para a busca.
    if not projeto.arquivo_pdf:
        messages.error(
            request,
            'Anexe o PDF do projeto (campo "Documento (PDF)") antes de '
            'enviar para avaliação por pares.',
        )
        return redirect('projeto_detalhe', pk=projeto.pk)
    if not projeto.resumo.strip():
        messages.error(
            request,
            'Preencha o resumo do projeto antes de enviar para avaliação.',
        )
        return redirect('projeto_detalhe', pk=projeto.pk)

    projeto.status_avaliacao = 'submetido'
    projeto.save()
    messages.success(
        request,
        'Projeto enviado para avaliação por pares. '
        'O técnico da DIP irá alocar os avaliadores.',
    )
    return redirect('projeto_detalhe', pk=projeto.pk)


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
        form = ProjetoForm(request.POST, request.FILES)
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
        form = ProjetoForm(request.POST, request.FILES, instance=projeto)
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
