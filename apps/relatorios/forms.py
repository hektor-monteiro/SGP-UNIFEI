"""Formulários do módulo de Planos de Trabalho e Relatórios."""
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PlanoTrabalho, Relatorio


class PlanoTrabalhoForm(forms.ModelForm):
    """Formulário de criação/edição de plano de trabalho.

    Regras de negócio:
    - Um plano por bolsa (1:1)
    - Aluno e projeto são derivados da bolsa selecionada (coerência garantida:
      plano ↔ bolsa ↔ projeto do docente)
    - Aluno não altera o status (campo desabilitado pela view)
    """

    class Meta:
        model = PlanoTrabalho
        fields = [
            'bolsa', 'titulo', 'descricao', 'objetivos',
            'metodologia', 'cronograma', 'status',
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
            'objetivos': forms.Textarea(attrs={'rows': 3}),
            'metodologia': forms.Textarea(attrs={'rows': 3}),
            'cronograma': forms.Textarea(
                attrs={'rows': 4, 'placeholder': '{"Semana 1": "Revisão bibliográfica", ...}'},
            ),
        }

    def __init__(self, *args, bolsas=None, pode_mudar_status=True, **kwargs):
        """`bolsas`: restringe as bolsas disponíveis; `pode_mudar_status`: False para aluno."""
        super().__init__(*args, **kwargs)
        if bolsas is not None:
            self.fields['bolsa'].queryset = bolsas
        self.fields['bolsa'].empty_label = '— Selecione a bolsa —'
        if not pode_mudar_status:
            # Aluno mantém o status atual (submissão/aprovação é do docente/DIP)
            self.fields['status'].disabled = True

    def clean(self):
        cleaned = super().clean()
        bolsa = cleaned.get('bolsa')
        if bolsa:
            # Regra: um plano por bolsa
            qs = PlanoTrabalho.objects.filter(bolsa=bolsa)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f'A bolsa de {bolsa.aluno.nome} em {bolsa.projeto.codigo} '
                    'já possui plano de trabalho.'
                )
        return cleaned

    def save(self, commit=True):
        """Deriva aluno e projeto da bolsa e carimba o fluxo de aprovação."""
        instance = super().save(commit=False)
        if instance.bolsa_id:
            instance.aluno = instance.bolsa.aluno
            instance.projeto = instance.bolsa.projeto
        if instance.cronograma is None:
            instance.cronograma = {}
        if instance.status in ('submetido', 'aprovado', 'reprovado') and not instance.data_submissao:
            instance.data_submissao = timezone.now()
        if instance.status == 'aprovado' and not instance.data_aprovacao:
            instance.data_aprovacao = timezone.now()
        if commit:
            instance.save()
        return instance


class RelatorioForm(forms.ModelForm):
    """Formulário de criação/edição de relatório (parcial ou final).

    Regras de negócio:
    - Um relatório FINAL por bolsa (é o relatório de encerramento);
      parciais podem se repetir (um por período)
    - Aluno é derivado da bolsa selecionada (coerência garantida)
    - Status, nota e observações NÃO são campos do formulário: o fluxo é
      feito por ações dedicadas (submeter/avaliar) nas views
    """

    class Meta:
        model = Relatorio
        fields = ['bolsa', 'tipo', 'titulo', 'conteudo', 'periodo_inicio', 'periodo_fim']
        widgets = {
            'conteudo': forms.Textarea(attrs={'rows': 6}),
            'periodo_inicio': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'periodo_fim': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, bolsas=None, **kwargs):
        """`bolsas`: restringe as bolsas disponíveis para vincular."""
        super().__init__(*args, **kwargs)
        if bolsas is not None:
            self.fields['bolsa'].queryset = bolsas
        self.fields['bolsa'].empty_label = '— Selecione a bolsa —'
        self.fields['tipo'].empty_label = '— Selecione o tipo —'

    def clean(self):
        cleaned = super().clean()
        bolsa = cleaned.get('bolsa')
        tipo = cleaned.get('tipo')
        inicio = cleaned.get('periodo_inicio')
        fim = cleaned.get('periodo_fim')

        if inicio and fim and inicio > fim:
            raise ValidationError(
                'O início do período não pode ser posterior ao fim.',
            )

        if bolsa and tipo == 'final':
            # Regra: apenas um relatório final por bolsa (encerramento)
            qs = Relatorio.objects.filter(bolsa=bolsa, tipo='final')
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f'A bolsa de {bolsa.aluno.nome} em {bolsa.projeto.codigo} '
                    'já possui relatório final.'
                )
        return cleaned

    def save(self, commit=True):
        """Deriva o aluno da bolsa selecionada."""
        instance = super().save(commit=False)
        if instance.bolsa_id:
            instance.aluno = instance.bolsa.aluno
        if commit:
            instance.save()
        return instance


class AvaliacaoRelatorioForm(forms.Form):
    """Avaliação do relatório: nota de 0 a 10 + observações em texto livre.

    A view aplica a aprovação automática pela nota mínima.
    """

    nota = forms.DecimalField(
        label='Nota (0 a 10)',
        min_value=Decimal('0'),
        max_value=Decimal('10'),
        max_digits=4,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'step': '0.25', 'min': '0', 'max': '10'}),
    )
    observacoes = forms.CharField(
        label='Observações / parecer',
        required=False,
        widget=forms.Textarea(attrs={'rows': 5}),
    )
