"""Formulários do módulo de Editais."""
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User

from apps.bolsas.models import ModalidadeBolsa
from apps.core.forms import BuscaNomeMixin
from apps.core.models import Perfil
from apps.projetos.models import Proposta

from .models import CriterioAvaliacao, Edital


class EditalForm(forms.ModelForm):
    """Formulário de criação/edição de edital.

    O status NÃO é editável aqui: muda apenas pelas ações do fluxo
    (aprovar/iniciar/encerrar/cancelar). `criado_por` é definido pela view.
    """

    class Meta:
        model = Edital
        fields = [
            'codigo', 'titulo', 'descricao', 'arquivo_pdf',
            'data_inicio', 'data_fim', 'modalidade', 'nota_minima',
        ]
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
        # O PDF nasce opcional (rascunho sem documento); a exigência é
        # na aprovação — ver view `acao`.
        self.fields['arquivo_pdf'].required = False

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get('data_inicio')
        data_fim = cleaned.get('data_fim')
        if data_inicio and data_fim and data_fim < data_inicio:
            raise forms.ValidationError(
                'A data de término deve ser posterior à data de início.'
            )
        return cleaned


class PropostaForm(forms.ModelForm):
    """Formulário de submissão de proposta a um edital (somente docente).

    A proposta solicita cotas de bolsa para um projeto; `edital`,
    `submetido_por` e `status` são definidos pela view. `projetos`
    restringe os projetos disponíveis ao docente.
    """

    class Meta:
        model = Proposta
        fields = ['projeto', 'titulo', 'cotas', 'resumo']
        widgets = {
            'resumo': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, projetos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['resumo'].required = False
        # Cotas sem projeto não fazem sentido: obrigatório mesmo no model
        # aceitando nulo (propostas antigas sem vínculo).
        self.fields['projeto'].required = True
        self.fields['projeto'].empty_label = '— Selecione o projeto —'
        self.fields['cotas'].required = True
        if projetos is not None:
            self.fields['projeto'].queryset = projetos


class CriterioForm(forms.ModelForm):
    """Formulário de criação/edição de critério de avaliação (técnico+)."""

    class Meta:
        model = CriterioAvaliacao
        fields = ['nome', 'escopo', 'descricao', 'peso', 'ativo']
        widgets = {
            'descricao': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_peso(self):
        peso = self.cleaned_data.get('peso')
        if peso is not None and peso <= 0:
            raise forms.ValidationError('O peso deve ser maior que zero.')
        return peso


class DocenteChoiceField(forms.ModelChoiceField):
    """Rótulo do docente pelo **nome**, não pelo login.

    Exibe "Nome completo (username)" — assim o técnico digita o nome no
    campo de busca (`busca_nome.js`) em vez de decorar o login.
    """

    def label_from_instance(self, obj):
        pessoa = getattr(getattr(obj, 'perfil', None), 'pessoa', None)
        nome = getattr(pessoa, 'nome', None) or obj.get_full_name() or obj.username
        return f'{nome} ({obj.username})'


class AlocacaoForm(BuscaNomeMixin, forms.Form):
    """Seleção do docente que vai avaliar a proposta ou o projeto.

    `excluir_pessoas` remove da lista os membros da equipe do projeto
    (regra de paridade: quem participa não avalia o próprio projeto).
    """
    campos_busca = ('avaliador',)

    avaliador = DocenteChoiceField(
        queryset=User.objects.filter(
            perfil__perfil=Perfil.PERFIL_DOCENTE,
        ).select_related('perfil__pessoa').order_by(
            'perfil__pessoa__nome', 'username',
        ),
        label='Docente avaliador',
        empty_label='— Selecione o docente —',
    )

    def __init__(self, *args, excluir_pessoas=None, **kwargs):
        super().__init__(*args, **kwargs)
        if excluir_pessoas:
            self.fields['avaliador'].queryset = (
                self.fields['avaliador'].queryset.exclude(
                    perfil__pessoa_id__in=excluir_pessoas,
                )
            )


class AvaliacaoForm(forms.Form):
    """Notas de 0 a 10 por critério ativo + parecer em texto livre.

    Os campos de nota são criados dinamicamente a partir dos critérios
    ativos; a view calcula a nota final como média ponderada pelos pesos.
    """

    def __init__(self, *args, criterios=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.criterios = list(criterios or [])
        for criterio in self.criterios:
            self.fields[f'nota_{criterio.pk}'] = forms.DecimalField(
                label=f'{criterio.nome} (peso {criterio.peso})',
                min_value=Decimal('0'),
                max_value=Decimal('10'),
                max_digits=4,
                decimal_places=2,
                widget=forms.NumberInput(attrs={'step': '0.25', 'min': '0', 'max': '10'}),
            )
        self.fields['parecer'] = forms.CharField(
            label='Parecer',
            required=False,
            widget=forms.Textarea(attrs={'rows': 5}),
        )
        # Notas primeiro, parecer por último
        self.order_fields(
            [f'nota_{c.pk}' for c in self.criterios] + ['parecer']
        )
