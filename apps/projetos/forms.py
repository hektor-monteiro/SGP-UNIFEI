"""Formulários do módulo de Projetos."""
from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from .models import Pessoa, Projeto, gerar_codigo_projeto

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
        # _state.adding: detecção correta de "criação" — o pk do Projeto é
        # UUID com default e já nasce preenchido (instance.pk nunca é None)
        if self.instance._state.adding:
            self.fields['data_registro'].initial = date.today()
            self.fields['status'].initial = 'vigente'
            # Código gerado pelo sistema (próximo sequencial PVDI###-AAAA);
            # pode ser sobrescrito quando o nº vem de registro externo
            self.fields['codigo'].required = False
            self.fields['codigo'].initial = gerar_codigo_projeto()
            self.fields['codigo'].help_text = (
                'Deixe em branco para gerar automaticamente '
                '(formato PVDI###-AAAA).'
            )

    def clean(self):
        cleaned = super().clean()

        # Criação sem código: gera o sequencial único no padrão da DIP
        codigo = cleaned.get('codigo')
        if codigo:
            cleaned['codigo'] = codigo.strip()
        elif self.instance._state.adding:
            cleaned['codigo'] = gerar_codigo_projeto(
                cleaned.get('data_registro'),
            )

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
