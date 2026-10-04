"""Formulários do módulo de Editais."""
from django import forms

from apps.bolsas.models import ModalidadeBolsa

from .models import Edital


class EditalForm(forms.ModelForm):
    """Formulário de criação/edição de edital.

    O status NÃO é editável aqui: muda apenas pelas ações do fluxo
    (publicar/iniciar/encerrar/cancelar). `criado_por` é definido pela view.
    """

    class Meta:
        model = Edital
        fields = ['codigo', 'titulo', 'descricao', 'data_inicio', 'data_fim', 'modalidade']
        widgets = {
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['modalidade'].queryset = ModalidadeBolsa.objects.filter(ativo=True)
        self.fields['modalidade'].empty_label = '— Selecione a modalidade —'
        self.fields['modalidade'].required = False
        self.fields['descricao'].required = False

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get('data_inicio')
        data_fim = cleaned.get('data_fim')
        if data_inicio and data_fim and data_fim < data_inicio:
            raise forms.ValidationError(
                'A data de término deve ser posterior à data de início.'
            )
        return cleaned
