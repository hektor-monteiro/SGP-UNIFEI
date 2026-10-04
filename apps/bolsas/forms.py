"""Formulários do módulo de Bolsas."""
from django import forms
from django.core.exceptions import ValidationError

from apps.projetos.models import Pessoa

from .models import Bolsa, ModalidadeBolsa


class BolsaForm(forms.ModelForm):
    """Formulário de criação/edição de bolsa.

    Regras de negócio validadas:
    - 1 bolsa ativa por aluno (requisito §2)
    - Aluno do formulário deve ser do tipo 'aluno'
    - Data de término posterior à de início
    """

    class Meta:
        model = Bolsa
        fields = [
            'aluno', 'modalidade', 'projeto', 'fomentador',
            'data_inicio', 'data_fim', 'status', 'valor_mensal',
        ]
        widgets = {
            # format='%Y-%m-%d': o input date do HTML exige AAAA-MM-DD
            'data_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, projetos=None, **kwargs):
        """`projetos`: restringe os projetos disponíveis (docente: só os que coordena)."""
        super().__init__(*args, **kwargs)
        self.fields['aluno'].queryset = Pessoa.objects.filter(tipo='aluno', ativo=True)
        self.fields['aluno'].empty_label = '— Selecione o aluno —'
        self.fields['modalidade'].queryset = ModalidadeBolsa.objects.filter(ativo=True)
        self.fields['modalidade'].empty_label = '— Selecione a modalidade —'
        if projetos is not None:
            self.fields['projeto'].queryset = projetos
        self.fields['fomentador'].required = False
        self.fields['valor_mensal'].required = False

    def clean(self):
        cleaned = super().clean()
        aluno = cleaned.get('aluno')
        data_inicio = cleaned.get('data_inicio')
        data_fim = cleaned.get('data_fim')
        status = cleaned.get('status')

        if data_inicio and data_fim and data_fim < data_inicio:
            raise ValidationError(
                'A data de término deve ser posterior à data de início.'
            )

        # Regra: 1 bolsa ativa por aluno
        if status == 'ativa' and aluno:
            outra = Bolsa.objects.filter(aluno=aluno, status='ativa')
            if self.instance and self.instance.pk:
                outra = outra.exclude(pk=self.instance.pk)
            existente = outra.select_related('modalidade', 'projeto').first()
            if existente:
                raise ValidationError(
                    f'{aluno.nome} já possui bolsa ativa: '
                    f'{existente.modalidade.sigla} em {existente.projeto.codigo} '
                    f'({existente.data_inicio:%d/%m/%Y} a {existente.data_fim:%d/%m/%Y}). '
                    'Encerre ou cancele a bolsa atual antes de criar outra.'
                )
        return cleaned
