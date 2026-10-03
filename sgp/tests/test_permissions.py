"""Testes de autenticação e permissões por perfil."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil


class PerfilModelTests(TestCase):
    """Testes do modelo Perfil e hierarquia de permissões."""

    def setUp(self):
        self.user_aluno = User.objects.create_user('aluno', password='x')
        self.user_tecnico = User.objects.create_user('tecnico', password='x')
        self.user_diretor = User.objects.create_user('diretor', password='x')
        self.user_proreitor = User.objects.create_user('proreitor', password='x')
        self.user_sem_perfil = User.objects.create_user('semperfil', password='x')

        Perfil.objects.create(user=self.user_aluno, perfil=Perfil.PERFIL_ALUNO)
        Perfil.objects.create(user=self.user_tecnico, perfil=Perfil.PERFIL_TECNICO)
        Perfil.objects.create(user=self.user_diretor, perfil=Perfil.PERFIL_DIRETOR)
        Perfil.objects.create(user=self.user_proreitor, perfil=Perfil.PERFIL_PROREITOR)

    def test_nivel_hierarquico(self):
        """Níveis crescentes: aluno(1) < tecnico(3) < diretor(4) < proreitor(5)."""
        self.assertEqual(self.user_aluno.perfil.nivel, 1)
        self.assertEqual(self.user_tecnico.perfil.nivel, 3)
        self.assertEqual(self.user_diretor.perfil.nivel, 4)
        self.assertEqual(self.user_proreitor.perfil.nivel, 5)

    def test_pelo_menos(self):
        """pelo_menos compara nível hierárquico."""
        self.assertTrue(self.user_proreitor.perfil.pelo_menos('diretor'))
        self.assertTrue(self.user_diretor.perfil.pelo_menos('diretor'))
        self.assertFalse(self.user_tecnico.perfil.pelo_menos('diretor'))
        self.assertTrue(self.user_tecnico.perfil.pelo_menos('aluno'))

    def test_tem_perfil(self):
        """tem_perfil verifica lista de perfis permitidos."""
        self.assertTrue(self.user_aluno.perfil.tem_perfil('aluno', 'docente'))
        self.assertFalse(self.user_aluno.perfil.tem_perfil('diretor', 'proreitor'))


class AutenticacaoTests(TestCase):
    """Testes de login/logout e acesso ao painel."""

    def test_painel_redireciona_para_login(self):
        """Usuário não autenticado é redirecionado ao login."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_login_com_credenciais_validas(self):
        """Login com credenciais válidas funciona."""
        User.objects.create_user('joao', password='senha123')
        ok = self.client.login(username='joao', password='senha123')
        self.assertTrue(ok)
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_home_e_publica(self):
        """A home é acessível sem autenticação."""
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)

    def test_usuario_sem_perfil_ve_aviso(self):
        """Usuário autenticado sem Perfil vê aviso no painel."""
        User.objects.create_user('orfaos', password='x')
        self.client.login(username='orfaos', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'perfil de acesso definido')


class VisaoGeralTests(TestCase):
    """Testes de dados exibidos no painel conforme perfil."""

    def setUp(self):
        self.tecnico = User.objects.create_user('tec', password='x')
        Perfil.objects.create(user=self.tecnico, perfil=Perfil.PERFIL_TECNICO)
        self.aluno = User.objects.create_user('alu', password='x')
        Perfil.objects.create(user=self.aluno, perfil=Perfil.PERFIL_ALUNO)

    def test_tecnico_vê_visao_geral(self):
        """Técnico/diretor/pro-reitor veem estatísticas gerais."""
        self.client.login(username='tec', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Visão geral')

    def test_aluno_não_vê_visao_geral(self):
        """Aluno não vê estatísticas gerais (apenas sua área)."""
        self.client.login(username='alu', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Visão geral')
        self.assertContains(response, 'Minha área')
