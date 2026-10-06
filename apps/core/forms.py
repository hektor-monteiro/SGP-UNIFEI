"""Formulários do módulo core (busca de nomes) e do módulo LGPD (§6)."""
from django import forms

from .models import SolicitacaoLGPD


class BuscaNomeMixin:
    """Seleção de nomes com busca digitando + dropdown (padrão do projeto).

    Marca com a classe `busca-nome` os <select> listados em `campos_busca`.
    O JavaScript `apps/core/static/js/busca_nome.js` (incluído no
    `base.html`) insere o campo "Digite para filtrar…" acima do menu e
    filtra as opções enquanto o usuário digita — sem diferenciar acento
    nem caixa — mantendo o dropdown normal para quem não digita.

    Campos sem o nome em `campos_busca` são ignorados, então o mixin pode
    ser declarado com a lista fixa mesmo quando um campo nem existe no
    formulário.
    """

    campos_busca: tuple = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome in self.campos_busca:
            if nome not in self.fields:
                continue
            attrs = self.fields[nome].widget.attrs
            attrs['class'] = f"{attrs.get('class', '')} busca-nome".strip()


_STATUS_TRATAMENTO = [
    (SolicitacaoLGPD.STATUS_EM_ANALISE, 'Em análise'),
    (SolicitacaoLGPD.STATUS_CONCLUIDA, 'Concluída'),
    (SolicitacaoLGPD.STATUS_INDEFERIDA, 'Indeferida'),
]


class SolicitacaoLGPDForm(forms.ModelForm):
    """Criação de solicitação pelo próprio titular."""

    class Meta:
        model = SolicitacaoLGPD
        fields = ['tipo', 'descricao']
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': (
                    'Correção: descreva o dado incorreto e o valor correto. '
                    'Exclusão: explique o porquê da solicitação.'
                ),
            }),
        }

    def __init__(self, *args, titular=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.titular = titular

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        if tipo and self.titular is not None:
            duplicada = SolicitacaoLGPD.objects.filter(
                titular=self.titular,
                tipo=tipo,
                status__in=(
                    SolicitacaoLGPD.STATUS_ABERTA,
                    SolicitacaoLGPD.STATUS_EM_ANALISE,
                ),
            ).exists()
            if duplicada:
                raise forms.ValidationError(
                    'Você já possui uma solicitação deste tipo em aberto. '
                    'Aguarde o tratamento pelo encarregado.'
                )
        return cleaned


class TratarSolicitacaoForm(forms.ModelForm):
    """Tratamento da solicitação pelo encarregado (técnicos+)."""

    class Meta:
        model = SolicitacaoLGPD
        fields = ['status', 'justificativa']
        widgets = {
            'justificativa': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': (
                    'Obrigatória ao concluir ou indeferir: informe o que '
                    'foi feito ou o motivo da recusa.'
                ),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = _STATUS_TRATAMENTO

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        justificativa = cleaned.get('justificativa')
        if (
            status in (SolicitacaoLGPD.STATUS_CONCLUIDA,
                       SolicitacaoLGPD.STATUS_INDEFERIDA)
            and not justificativa
        ):
            raise forms.ValidationError(
                'Informe a justificativa para concluir ou indeferir.'
            )
        return cleaned
