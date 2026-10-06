"""Testes do padrão de busca digitando nas seleções de nome.

Padrão do projeto: campos de pessoa (avaliador, coordenador, aluno,
membro de equipe) são marcados com `busca-nome` pelo `BuscaNomeMixin` e
o `base.html` carrega `js/busca_nome.js`, que insere o campo "Digite
para filtrar…" acima do dropdown.
"""
from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.bolsas.forms import BolsaForm, IndicacaoForm
from apps.core.forms import BuscaNomeMixin
from apps.core.models import Perfil
from apps.editais.forms import AlocacaoForm
from apps.editais.models import Edital
from apps.equipes.forms import MembroEquipeForm
from apps.projetos.forms import ProjetoForm
from apps.projetos.models import Pessoa, Proposta


def _criar_usuario(username, perfil):
    """Cria usuário com Perfil e Pessoa vinculada."""
    user = User.objects.create_user(username, password='x')
    p = Perfil.objects.create(user=user, perfil=perfil)
    p.pessoa = Pessoa.objects.create(
        nome=username.title(),
        email=f'{username}@test.com',
        tipo='aluno' if perfil == Perfil.PERFIL_ALUNO else perfil,
    )
    p.save()
    return user


class CamposComBuscaTests(TestCase):
    """Os campos de pessoa recebem a classe `busca-nome`."""

    def test_avaliador_da_alocacao_tem_busca(self):
        campo = AlocacaoForm().fields['avaliador']
        self.assertIn('busca-nome', campo.widget.attrs['class'])

    def test_rotulo_do_avaliador_mostra_o_nome_completo(self):
        """A busca é por nome: o rótulo precisa virar "Nome (username)"."""
        user = _criar_usuario('doc_rotulo', Perfil.PERFIL_DOCENTE)
        campo = AlocacaoForm().fields['avaliador']
        self.assertEqual(
            campo.label_from_instance(user),
            f'{user.perfil.pessoa.nome} ({user.username})',
        )

    def test_coordenador_do_projeto_tem_busca(self):
        campo = ProjetoForm().fields['coordenador']
        self.assertIn('busca-nome', campo.widget.attrs['class'])

    def test_aluno_da_bolsa_tem_busca(self):
        campo = BolsaForm().fields['aluno']
        self.assertIn('busca-nome', campo.widget.attrs['class'])

    def test_aluno_da_indicacao_tem_busca(self):
        campo = IndicacaoForm().fields['aluno']
        self.assertIn('busca-nome', campo.widget.attrs['class'])

    def test_pessoa_da_equipe_tem_busca(self):
        campo = MembroEquipeForm().fields['pessoa']
        self.assertIn('busca-nome', campo.widget.attrs['class'])

    def test_campos_fora_da_lista_nao_sao_marcados(self):
        campo = ProjetoForm().fields['titulo']
        self.assertNotIn('busca-nome', campo.widget.attrs.get('class', ''))

    def test_campo_inexistente_nao_quebra_o_formulario(self):
        class FormularioDeTeste(BuscaNomeMixin, forms.Form):
            campos_busca = ('nao_existe',)
            nome = forms.CharField()

        campo = FormularioDeTeste().fields['nome']
        self.assertNotIn('busca-nome', campo.widget.attrs)


class PaginaComBuscaTests(TestCase):
    """As páginas carregam o script e renderizam a classe no <select>."""

    def test_arquivo_do_javascript_e_encontrado(self):
        self.assertIsNotNone(finders.find('js/busca_nome.js'))

    def test_index_carrega_o_script_da_busca(self):
        response = self.client.get(reverse('index'))
        self.assertContains(response, 'busca_nome.js')

    def test_formulario_de_novo_projeto_renderiza_a_busca(self):
        _criar_usuario('doc_busca', Perfil.PERFIL_DOCENTE)
        self.client.login(username='doc_busca', password='x')
        response = self.client.get(reverse('projeto_novo'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'busca-nome')
        self.assertContains(response, 'busca_nome.js')

    def test_pagina_de_alocacao_renderiza_a_busca(self):
        hoje = localdate()
        edital = Edital.objects.create(
            codigo='EDITAL-BUSCA',
            titulo='Edital da busca',
            data_inicio=hoje - timedelta(days=1),
            data_fim=hoje + timedelta(days=30),
            status='em_andamento',
        )
        aluno = _criar_usuario('alu_busca', Perfil.PERFIL_ALUNO)
        proposta = Proposta.objects.create(
            titulo='Proposta da busca',
            edital=edital,
            submetido_por=aluno.perfil.pessoa,
        )
        _criar_usuario('tec_busca', Perfil.PERFIL_TECNICO)
        self.client.login(username='tec_busca', password='x')
        response = self.client.get(
            reverse('proposta_alocar', kwargs={'pk': proposta.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'busca-nome')
