"""Formulários do módulo de Equipes (§3.8)."""
from django import forms

from apps.projetos.models import Pessoa

from .models import MembroEquipe


class MembroEquipeForm(forms.ModelForm):
    """Cadastro de membro de equipe.

    Regras validadas:
    - Data de saída não anterior à data de entrada
    - Sem duplicidade de (projeto, pessoa, função)
    - `ativo` é derivado da data de saída no save (sem saída → ativo)
    """

    class Meta:
        model = MembroEquipe
        fields = ['pessoa', 'funcao', 'carga_horaria', 'data_entrada', 'data_saida']
        widgets = {
            # format='%Y-%m-%d': o input date do HTML exige AAAA-MM-DD
            'data_entrada': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'data_saida': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, projeto=None, **kwargs):
        """`projeto`: projeto dono da equipe (validação de duplicidade e save)."""
        super().__init__(*args, **kwargs)
        self.projeto = projeto
        self.fields['pessoa'].queryset = Pessoa.objects.filter(
            ativo=True,
        ).order_by('nome')
        self.fields['pessoa'].empty_label = '— Selecione a pessoa —'
        self.fields['carga_horaria'].required = False
        self.fields['data_saida'].required = False

    def clean(self):
        """Valida período e duplicidade (após todos os campos limpos)."""
        cleaned = super().clean()
        pessoa = cleaned.get('pessoa')
        funcao = cleaned.get('funcao')
        entrada = cleaned.get('data_entrada')
        saida = cleaned.get('data_saida')

        if entrada and saida and saida < entrada:
            self.add_error(
                'data_saida',
                'A data de saída não pode ser anterior à data de entrada.',
            )

        # Duplicidade aqui e não em clean_pessoa: 'funcao' ainda não existe
        # no cleaned_data quando 'pessoa' é limpo (ordem dos campos).
        if pessoa and funcao and self.projeto:
            duplicados = MembroEquipe.objects.filter(
                projeto=self.projeto, pessoa=pessoa, funcao=funcao,
            )
            if self.instance.pk:
                duplicados = duplicados.exclude(pk=self.instance.pk)
            if duplicados.exists():
                self.add_error(
                    'pessoa',
                    'Esta pessoa já integra a equipe deste projeto com esta função.',
                )
        return cleaned

    def save(self, commit=True):
        """Vincula o projeto e deriva `ativo` da data de saída."""
        if self.projeto is not None:
            self.instance.projeto = self.projeto
        self.instance.ativo = self.instance.data_saida is None
        return super().save(commit)


class JustificativaExclusaoForm(forms.Form):
    """Justificativa obrigatória para excluir um membro da equipe (§3.8).

    O texto é anexado ao registro da exclusão no log de auditoria LGPD
    (§6) — a exclusão apaga o cadastro, mas a justificativa permanece.
    """

    justificativa = forms.CharField(
        label='Justificativa da exclusão',
        max_length=1000,
        help_text=(
            'Motivo da exclusão do membro. Fica registrada no log de '
            'auditoria LGPD junto da exclusão.'
        ),
        widget=forms.Textarea(attrs={'rows': 4, 'autofocus': True}),
        error_messages={
            'required': 'Informe a justificativa da exclusão do membro.',
            'max_length': 'A justificativa pode ter no máximo 1000 caracteres.',
        },
    )
