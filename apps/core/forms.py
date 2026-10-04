"""Formulários do módulo LGPD (§6): solicitações de titular."""
from django import forms

from .models import SolicitacaoLGPD

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
