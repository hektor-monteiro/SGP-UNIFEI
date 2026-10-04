"""Formulários do módulo de Projetos."""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import Pessoa, Projeto

# Máximo de projetos sem fomento por coordenador (regra de negócio da DIP)
MAX_PROJETOS_SEM_FOMENTO = 2


class ProjetoForm(forms.ModelForm):
    """Formulário de criação/edição de projeto de pesquisa."""

    class Meta:
        model = Projeto
        fields = [
            'codigo', 'titulo', 'descricao', 'data_registro',
            'data_inicio', 'data_termino', 'status',
            'fomentador', 'recursos_internos', 'recursos_externos',
            'coordenador', 'processo_sipac', 'instituicao',
        ]
        widgets = {
            # format='%Y-%m-%d': o input date do HTML exige AAAA-MM-DD;
            # sem isso o Django renderiza dd/mm/aaaa e o navegador mostra em branco
            'data_registro': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_termino': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'descricao': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['coordenador'].queryset = Pessoa.objects.filter(
            tipo='docente', ativo=True,
        )
        self.fields['coordenador'].empty_label = '— Selecione o docente —'
        self.fields['data_termino'].required = False
        self.fields['descricao'].required = False
        if not self.instance.pk:
            self.fields['data_registro'].initial = date.today()
            self.fields['status'].initial = 'vigente'

    def clean(self):
        cleaned = super().clean()
        coordenador = cleaned.get('coordenador')
        fomentador = cleaned.get('fomentador')

        # Regra: docente pode coordenar no máximo 2 projetos SEM fomento
        if coordenador and not fomentador:
            qs = Projeto.objects.filter(
                coordenador=coordenador, fomentador__isnull=True,
            )
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.count() >= MAX_PROJETOS_SEM_FOMENTO:
                raise ValidationError(
                    'Regra de negócio: um docente pode coordenar no máximo '
                    f'{MAX_PROJETOS_SEM_FOMENTO} projetos sem fomento. '
                    'Vincule um fomentador ao projeto ou escolha outro coordenador.'
                )
        return cleaned
