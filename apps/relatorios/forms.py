"""Formulários do módulo de Planos de Trabalho."""
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PlanoTrabalho


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
