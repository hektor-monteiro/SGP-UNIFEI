"""Formulários do módulo de Comprovantes.

Cada tipo de comprovante tem seu formulário de emissão; o objeto comprova
a elegibilidade (bolsa própria/orientada, participação na equipe ou
avaliação realizada) e a view monta o registro com os dados do sistema.
"""
from django import forms

from apps.bolsas.models import Bolsa
from apps.editais.models import Avaliacao
from apps.projetos.models import Pessoa, Projeto
from apps.relatorios.models import Relatorio


def integra_equipe(pessoa, projeto) -> bool:
    """Pessoa é coordenadora ou membro (qualquer função) do projeto."""
    if projeto.coordenador_id and projeto.coordenador_id == pessoa.id:
        return True
    return projeto.membros.filter(pessoa=pessoa).exists()


class ComprovanteBolsaForm(forms.Form):
    """Emissão de comprovante de bolsa (aluno beneficiário ou orientando)."""

    bolsa = forms.ModelChoiceField(
        label='Bolsa',
        queryset=Bolsa.objects.none(),
        empty_label='— Selecione a bolsa —',
    )

    def __init__(self, *args, bolsas=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bolsas is not None:
            self.fields['bolsa'].queryset = bolsas


class ComprovanteParticipacaoForm(forms.Form):
    """Emissão de comprovante de participação em projeto.

    O beneficiário é o próprio usuário; técnico+ pode emitir para
    qualquer pessoa (campo `pessoa` habilitado).
    """

    projeto = forms.ModelChoiceField(
        label='Projeto',
        queryset=Projeto.objects.none(),
        empty_label='— Selecione o projeto —',
    )
    pessoa = forms.ModelChoiceField(
        label='Beneficiário',
        queryset=Pessoa.objects.none(),
        empty_label='— Selecione a pessoa —',
        required=False,
    )

    def __init__(self, *args, projetos=None, perfil=None,
                 pode_escolher_pessoa=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil
        self.pode_escolher_pessoa = pode_escolher_pessoa
        if projetos is not None:
            self.fields['projeto'].queryset = projetos
        if pode_escolher_pessoa:
            self.fields['pessoa'].queryset = Pessoa.objects.all()
            self.fields['pessoa'].required = True
        else:
            # Beneficiário sempre o próprio usuário
            del self.fields['pessoa']

    def clean(self):
        cleaned = super().clean()
        projeto = cleaned.get('projeto')
        if not projeto:
            return cleaned

        if self.pode_escolher_pessoa:
            pessoa = cleaned.get('pessoa')
        else:
            pessoa = self.perfil.pessoa if self.perfil else None

        if pessoa is None:
            raise forms.ValidationError(
                'Seu usuário não possui vínculo de pessoa; procure a DIP.',
            )
        if not integra_equipe(pessoa, projeto):
            raise forms.ValidationError(
                f'{pessoa.nome} não integra a equipe do projeto {projeto.codigo}.',
            )
        cleaned['pessoa_beneficiada'] = pessoa
        return cleaned


class ComprovanteAvaliacaoForm(forms.Form):
    """Emissão de comprovante de avaliação.

    Exige exatamente uma origem: relatório avaliado ou avaliação de
    proposta concluída. O beneficiário é derivado do próprio registro
    (avaliador), garantindo que só avaliações reais gerem comprovante.
    """

    relatorio = forms.ModelChoiceField(
        label='Relatório avaliado',
        queryset=Relatorio.objects.none(),
        empty_label='— Selecione —',
        required=False,
    )
    avaliacao = forms.ModelChoiceField(
        label='Avaliação de proposta',
        queryset=Avaliacao.objects.none(),
        empty_label='— Selecione —',
        required=False,
    )

    def __init__(self, *args, relatorios=None, avaliacoes=None, **kwargs):
        super().__init__(*args, **kwargs)
        if relatorios is not None:
            self.fields['relatorio'].queryset = relatorios
        if avaliacoes is not None:
            self.fields['avaliacao'].queryset = avaliacoes

    def clean(self):
        cleaned = super().clean()
        relatorio = cleaned.get('relatorio')
        avaliacao = cleaned.get('avaliacao')

        if bool(relatorio) == bool(avaliacao):
            raise forms.ValidationError(
                'Selecione exatamente uma opção: relatório ou avaliação de proposta.',
            )

        if relatorio:
            if relatorio.avaliado_por is None:
                raise forms.ValidationError(
                    'Este relatório não possui avaliador registrado.',
                )
            cleaned['pessoa_beneficiada'] = relatorio.avaliado_por
        else:
            # QS já garante avaliador com Perfil e Pessoa
            pessoa = getattr(getattr(avaliacao.avaliador, 'perfil', None), 'pessoa', None)
            if pessoa is None:
                raise forms.ValidationError(
                    'O avaliador desta avaliação não possui vínculo de pessoa.',
                )
            cleaned['pessoa_beneficiada'] = pessoa
        return cleaned
