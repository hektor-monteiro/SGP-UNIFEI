"""Views do módulo de Comprovantes.

Regras de acesso:
- Lista/Detalhe: beneficiário (pessoa) ou quem emitiu; técnico+ vê todos.
- Emissão:
  - Bolsa: aluno da bolsa, orientador/co-orientador do projeto ou técnico+;
  - Participação: coordenador ou membro do projeto (próprio beneficiário);
    técnico+ pode emitir para qualquer pessoa da equipe;
  - Avaliação: quem realizou a avaliação (relatório ou proposta);
    técnico+ pode emitir qualquer.
- Verificação: página pública pelo código de verificação (sem login).

TODO: gerar PDF da impressão e gravar em Comprovante.arquivo; hoje a
emissão é uma página HTML imprimível (browser → PDF).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.bolsas.models import Bolsa
from apps.core.models import Perfil
from apps.core.permissions import perfil_de, pode_gerir
from apps.editais.models import Avaliacao
from apps.projetos.models import Projeto
from apps.relatorios.models import Relatorio

from .forms import (
    ComprovanteAvaliacaoForm,
    ComprovanteBolsaForm,
    ComprovanteParticipacaoForm,
)
from .models import Comprovante


def _nota_texto(nota) -> str:
    """Formata nota decimal no padrão pt-BR (vírgula) para textos."""
    return f'{nota:.2f}'.replace('.', ',') if nota is not None else '—'


def _comprovantes_visiveis(user):
    """Comprovantes visíveis: técnico+ todos; demais, os próprios e os que emitiram."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return Comprovante.objects.all()
    if perfil is None or perfil.pessoa is None:
        return Comprovante.objects.none()
    return Comprovante.objects.filter(
        Q(pessoa=perfil.pessoa) | Q(emitido_por=user),
    )


def _bolsas_elegiveis(user):
    """Bolsas para comprovante: aluno as próprias; orientador/co-orientador
    as de seus orientandos; técnico+ todas."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return Bolsa.objects.all()
    if perfil is None or perfil.pessoa is None:
        return Bolsa.objects.none()
    if perfil.perfil == Perfil.PERFIL_ALUNO:
        return Bolsa.objects.filter(aluno=perfil.pessoa)
    return Bolsa.objects.filter(
        Q(projeto__coordenador=perfil.pessoa)
        | Q(projeto__membros__pessoa=perfil.pessoa,
            projeto__membros__funcao__in=('orientador', 'coorientador')),
    ).distinct()


def _projetos_elegiveis(user):
    """Projetos para comprovante de participação: coordenador ou membro."""
    perfil = perfil_de(user)
    if pode_gerir(perfil):
        return Projeto.objects.all()
    if perfil is None or perfil.pessoa is None:
        return Projeto.objects.none()
    return Projeto.objects.filter(
        Q(coordenador=perfil.pessoa) | Q(membros__pessoa=perfil.pessoa),
    ).distinct()


def _avaliacoes_de(user):
    """Origens de avaliação: técnico+ todos; demais, as realizadas por si.

    Retorna (relatórios avaliados, avaliações de proposta concluídas).
    """
    perfil = perfil_de(user)
    relatorios = Relatorio.objects.filter(
        avaliado_por__isnull=False, data_avaliacao__isnull=False,
    ).select_related('aluno', 'bolsa__modalidade')
    avaliacoes = Avaliacao.objects.filter(
        status='concluida',
        proposta__isnull=False,
        avaliador__perfil__pessoa__isnull=False,
    ).select_related('proposta', 'avaliador__perfil')

    if pode_gerir(perfil):
        return relatorios, avaliacoes

    if perfil is None or perfil.pessoa is None:
        return Relatorio.objects.none(), Avaliacao.objects.none()
    return (
        relatorios.filter(avaliado_por=perfil.pessoa),
        avaliacoes.filter(avaliador=user),
    )


def _emitir(request, tipo, pessoa, descricao, projeto=None, bolsa=None,
            edital=None, data_inicio=None, data_fim=None):
    """Cria o comprovante com o emitente carimbado e redireciona ao detalhe."""
    comprovante = Comprovante(
        tipo=tipo,
        pessoa=pessoa,
        descricao=descricao,
        projeto=projeto,
        bolsa=bolsa,
        edital=edital,
        data_inicio=data_inicio,
        data_fim=data_fim,
        emitido_por=request.user,
    )
    comprovante.save()
    messages.success(request, 'Comprovante emitido com sucesso.')
    return redirect('comprovante_detalhe', pk=comprovante.pk)


@login_required
@never_cache
def lista(request):
    """Lista de comprovantes com filtros por tipo e busca por beneficiário."""
    comprovantes = _comprovantes_visiveis(request.user)

    tipo = request.GET.get('tipo', '')
    busca = request.GET.get('q', '')
    if tipo:
        comprovantes = comprovantes.filter(tipo=tipo)
    if busca:
        comprovantes = comprovantes.filter(
            Q(pessoa__nome__icontains=busca) | Q(codigo_verificacao__icontains=busca),
        )

    perfil = perfil_de(request.user)
    contexto = {
        'comprovantes': comprovantes.select_related(
            'pessoa', 'projeto', 'bolsa__modalidade',
        ),
        'filtros': {'tipo': tipo, 'q': busca},
        'tipo_choices': Comprovante._meta.get_field('tipo').choices,
        'pode_emitir_bolsa': _bolsas_elegiveis(request.user).exists(),
        'pode_emitir_participacao': _projetos_elegiveis(request.user).exists(),
        'pode_emitir_avaliacao': any(
            qs.exists() for qs in _avaliacoes_de(request.user)
        ),
        'pode_gerir': pode_gerir(perfil),
    }
    return render(request, 'comprovantes/lista.html', contexto)


@login_required
@never_cache
def detalhe(request, pk):
    """Detalhe do comprovante (versão imprimível)."""
    comprovante = get_object_or_404(
        Comprovante.objects.select_related('pessoa', 'projeto', 'bolsa', 'edital'),
        pk=pk,
    )
    perfil = perfil_de(request.user)
    if not pode_gerir(perfil):
        if perfil is None or perfil.pessoa is None:
            raise PermissionDenied
        if comprovante.pessoa_id != perfil.pessoa.id and comprovante.emitido_por_id != request.user.id:
            raise PermissionDenied
    return render(request, 'comprovantes/detalhe.html', {'comprovante': comprovante})


@login_required
@never_cache
def emitir_bolsa(request):
    """Emissão de comprovante de bolsa (dados da bolsa no comprovante)."""
    bolsas = _bolsas_elegiveis(request.user)

    if request.method == 'POST':
        form = ComprovanteBolsaForm(request.POST, bolsas=bolsas)
        if form.is_valid():
            bolsa = form.cleaned_data['bolsa']
            return _emitir(
                request,
                tipo='bolsa',
                pessoa=bolsa.aluno,
                descricao=(
                    f'Comprovante de bolsa {bolsa.modalidade.sigla} no projeto '
                    f'{bolsa.projeto.codigo} — {bolsa.projeto.titulo}.'
                ),
                projeto=bolsa.projeto,
                bolsa=bolsa,
                data_inicio=bolsa.data_inicio,
                data_fim=bolsa.data_fim,
            )
    else:
        form = ComprovanteBolsaForm(bolsas=bolsas)

    return render(request, 'comprovantes/emitir.html', {
        'form': form,
        'titulo': 'Emitir comprovante de bolsa',
    })


@login_required
@never_cache
def emitir_participacao(request):
    """Emissão de comprovante de participação em projeto."""
    perfil = perfil_de(request.user)
    pode_gerir_user = pode_gerir(perfil)
    projetos = _projetos_elegiveis(request.user)

    if request.method == 'POST':
        form = ComprovanteParticipacaoForm(
            request.POST, projetos=projetos, perfil=perfil,
            pode_escolher_pessoa=pode_gerir_user,
        )
        if form.is_valid():
            projeto = form.cleaned_data['projeto']
            pessoa = form.cleaned_data['pessoa_beneficiada']
            membro = projeto.membros.filter(pessoa=pessoa).first()
            if projeto.coordenador_id == pessoa.id:
                descricao = f'Comprovante de coordenação do projeto {projeto.codigo} — {projeto.titulo}.'
            elif membro:
                descricao = (
                    f'Comprovante de participação no projeto {projeto.codigo} — '
                    f'{projeto.titulo} como {membro.get_funcao_display()}.'
                )
            else:
                descricao = f'Comprovante de participação no projeto {projeto.codigo} — {projeto.titulo}.'
            data_inicio = membro.data_entrada if membro else projeto.data_inicio
            data_fim = (membro.data_saida if membro and membro.data_saida else projeto.data_termino)
            return _emitir(
                request,
                tipo='participacao_projeto',
                pessoa=pessoa,
                descricao=descricao,
                projeto=projeto,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
    else:
        form = ComprovanteParticipacaoForm(
            projetos=projetos, perfil=perfil,
            pode_escolher_pessoa=pode_gerir_user,
        )

    return render(request, 'comprovantes/emitir.html', {
        'form': form,
        'titulo': 'Emitir comprovante de participação em projeto',
    })


@login_required
@never_cache
def emitir_avaliacao(request):
    """Emissão de comprovante de avaliação (relatório ou proposta)."""
    relatorios, avaliacoes = _avaliacoes_de(request.user)

    if request.method == 'POST':
        form = ComprovanteAvaliacaoForm(
            request.POST, relatorios=relatorios, avaliacoes=avaliacoes,
        )
        if form.is_valid():
            pessoa = form.cleaned_data['pessoa_beneficiada']
            relatorio = form.cleaned_data.get('relatorio')
            if relatorio:
                return _emitir(
                    request,
                    tipo='avaliacao',
                    pessoa=pessoa,
                    descricao=(
                        f'Avaliação do relatório {relatorio.get_tipo_display().lower()} '
                        f'"{relatorio.titulo}" ({relatorio.aluno.nome}) — nota {_nota_texto(relatorio.nota)}.'
                    ),
                    projeto=relatorio.bolsa.projeto,
                    bolsa=relatorio.bolsa,
                    data_inicio=relatorio.periodo_inicio,
                    data_fim=relatorio.periodo_fim,
                )
            avaliacao = form.cleaned_data['avaliacao']
            proposta = avaliacao.proposta
            return _emitir(
                request,
                tipo='avaliacao',
                pessoa=pessoa,
                descricao=(
                    f'Avaliação da proposta "{proposta.titulo}" — '
                    f'nota {_nota_texto(avaliacao.nota)}.'
                ),
                edital=proposta.edital,
                data_inicio=None,
                data_fim=None,
            )
    else:
        form = ComprovanteAvaliacaoForm(relatorios=relatorios, avaliacoes=avaliacoes)

    return render(request, 'comprovantes/emitir.html', {
        'form': form,
        'titulo': 'Emitir comprovante de avaliação',
    })


def verificar(request, codigo):
    """Verificação pública de um comprovante pelo código (sem login)."""
    comprovante = get_object_or_404(
        Comprovante.objects.select_related('pessoa', 'projeto', 'bolsa'),
        codigo_verificacao=codigo,
    )
    return render(request, 'comprovantes/verificar.html', {'comprovante': comprovante})
