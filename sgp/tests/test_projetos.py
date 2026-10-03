"""Testes do módulo de Projetos (views, permissões e regra de negócio)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, Instituicao
from apps.projetos.forms import MAX_PROJETOS_SEM_FOMENTO
from apps.projetos.models import Pessoa, Projeto


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _criar_projeto(coord, com_fomento=False):
    from apps.core.models import Fomentador
    fomentador = None
    if com_fomento:
        fomentador, _ = Fomentador.objects.get_or_create(
            sigla='FAPEMIG', defaults={'nome': 'FAPEMIG', 'tipo': 'projeto'},
        )
    return Projeto.objects.create(
        codigo=f'PVDI{Projeto.objects.count() + 1}-2026',
        titulo='Projeto de teste',
        data_registro=date.today(),
        data_inicio=date.today(),
        coordenador=coord,
        fomentador=fomentador,
    )


class ProjetoAcessoTests(TestCase):
    """Testes de acesso às views de projetos."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.docente_pessoa = Pessoa.objects.create(
            nome='Docente Teste', email='doc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno_pessoa = Pessoa.objects.create(
            nome='Aluno Teste', email='alu@alunos.edu.br', tipo='aluno', matricula='20260001', instituicao=inst,
        )
        self.projeto = _criar_projeto(self.docente_pessoa)
        self.user_docente = _criar_usuario('doc', Perfil.PERFIL_DOCENTE, self.docente_pessoa)
        self.user_aluno = _criar_usuario('alu', Perfil.PERFIL_ALUNO, self.aluno_pessoa)
        self.user_tecnico = _criar_usuario('tec', Perfil.PERFIL_TECNICO)
        self.user_diretor = _criar_usuario('dir', Perfil.PERFIL_DIRETOR)

    def test_lista_exige_login(self):
        response = self.client.get(reverse('projetos_lista'))
        self.assertEqual(response.status_code, 302)

    def test_docente_lista_seus_projetos(self):
        self.client.login(username='doc', password='x')
        response = self.client.get(reverse('projetos_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PVDI1-2026')

    def test_aluno_nao_ve_projetos_alheios(self):
        """Aluno não participante não vê o projeto na lista nem no detalhe."""
        self.client.login(username='alu', password='x')
        response = self.client.get(reverse('projetos_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'PVDI1-2026')
        response = self.client.get(reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}))
        self.assertEqual(response.status_code, 403)

    def test_aluno_participante_ve_detalhe(self):
        from apps.equipes.models import MembroEquipe
        MembroEquipe.objects.create(
            projeto=self.projeto, pessoa=self.aluno_pessoa,
            funcao='discente', data_entrada=date.today(),
        )
        self.client.login(username='alu', password='x')
        response = self.client.get(reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}))
        self.assertEqual(response.status_code, 200)

    def test_aluno_nao_pode_criar(self):
        self.client.login(username='alu', password='x')
        response = self.client.get(reverse('projeto_novo'))
        self.assertEqual(response.status_code, 403)

    def test_docente_pode_criar(self):
        self.client.login(username='doc', password='x')
        response = self.client.get(reverse('projeto_novo'))
        self.assertEqual(response.status_code, 200)

    def test_tecnico_pode_editar_qualquer_projeto(self):
        self.client.login(username='tec', password='x')
        response = self.client.get(reverse('projeto_editar', kwargs={'pk': self.projeto.pk}))
        self.assertEqual(response.status_code, 200)

    def test_docente_edita_proprio_projeto(self):
        self.client.login(username='doc', password='x')
        response = self.client.get(reverse('projeto_editar', kwargs={'pk': self.projeto.pk}))
        self.assertEqual(response.status_code, 200)

    def test_docente_nao_edita_projeto_alheio(self):
        outro = Pessoa.objects.create(
            nome='Outro Docente', email='doc2@unifei.edu.br', tipo='docente',
        )
        projeto_alheio = _criar_projeto(outro)
        self.client.login(username='doc', password='x')
        response = self.client.get(
            reverse('projeto_editar', kwargs={'pk': projeto_alheio.pk})
        )
        self.assertEqual(response.status_code, 403)


class RegraNegocioTests(TestCase):
    """Regra: máximo de projetos sem fomento por coordenador."""

    def setUp(self):
        self.docente = Pessoa.objects.create(
            nome='Docente Regra', email='regra@unifei.edu.br', tipo='docente',
        )
        self.user = _criar_usuario('doc_regra', Perfil.PERFIL_DOCENTE, self.docente)
        self.dados = {
            'codigo': 'NOVO-2026',
            'titulo': 'Novo projeto',
            'data_registro': date.today().isoformat(),
            'data_inicio': date.today().isoformat(),
            'status': 'vigente',
            'coordenador': self.docente.pk,
        }

    def test_limite_dois_sem_fomento(self):
        """Terceiro projeto sem fomento é rejeitado."""
        for _ in range(MAX_PROJETOS_SEM_FOMENTO):
            _criar_projeto(self.docente, com_fomento=False)
        self.client.login(username='doc_regra', password='x')
        response = self.client.post(reverse('projeto_novo'), self.dados)
        self.assertEqual(response.status_code, 200)  # volta ao form com erro
        self.assertContains(response, 'máximo')
        self.assertEqual(
            Projeto.objects.filter(coordenador=self.docente, fomentador__isnull=True).count(),
            MAX_PROJETOS_SEM_FOMENTO,
        )

    def test_sem_fomento_ilimitado_com_fomento(self):
        """Projetos COM fomento não contam para o limite."""
        for _ in range(MAX_PROJETOS_SEM_FOMENTO):
            _criar_projeto(self.docente, com_fomento=False)
        from apps.core.models import Fomentador
        fomentador, _ = Fomentador.objects.get_or_create(
            sigla='CNPq', defaults={'nome': 'CNPq', 'tipo': 'projeto'},
        )
        dados = {**self.dados, 'fomentador': fomentador.pk}
        self.client.login(username='doc_regra', password='x')
        response = self.client.post(reverse('projeto_novo'), dados)
        self.assertEqual(response.status_code, 302)  # sucesso → redireciona

    def test_criacao_como_coordenador_automatico(self):
        """Docente que cria projeto vira coordenador automaticamente."""
        self.client.login(username='doc_regra', password='x')
        response = self.client.post(reverse('projeto_novo'), self.dados)
        self.assertEqual(response.status_code, 302)
        projeto = Projeto.objects.get(codigo='NOVO-2026')
        self.assertEqual(projeto.coordenador, self.docente)
