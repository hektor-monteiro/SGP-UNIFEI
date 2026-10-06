"""Testes de submissão e gestão de propostas a editais."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.editais.models import Edital
from apps.projetos.models import Pessoa, Proposta


def _criar_usuario(username, perfil, com_pessoa=True):
    """Cria usuário com Perfil e, opcionalmente, Pessoa vinculada."""
    user = User.objects.create_user(username, password='x')
    p = Perfil.objects.create(user=user, perfil=perfil)
    if com_pessoa:
        pessoa = Pessoa.objects.create(
            nome=username.title(),
            email=f'{username}@test.com',
            tipo='aluno' if perfil == Perfil.PERFIL_ALUNO else perfil,
        )
        p.pessoa = pessoa
        p.save()
    return user


def _criar_edital(**kwargs):
    """Cria edital em andamento e vigente, a menos que informado o contrário."""
    hoje = localdate()
    dados = {
        'codigo': 'EDITAL-ABERTO',
        'titulo': 'Edital aberto de teste',
        'data_inicio': hoje - timedelta(days=10),
        'data_fim': hoje + timedelta(days=20),
        'status': 'em_andamento',
    }
    dados.update(kwargs)
    return Edital.objects.create(**dados)


class SubmissaoPropostaTests(TestCase):
    """Submissão de proposta: quem, quando e a que edital."""

    def setUp(self):
        self.edital = _criar_edital()
        self.aluno = _criar_usuario('alu_prop', Perfil.PERFIL_ALUNO)
        self.docente = _criar_usuario('doc_prop', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_prop', Perfil.PERFIL_TECNICO)
        self.url = reverse('proposta_nova', kwargs={'pk': self.edital.pk})

    def test_aluno_submete_proposta_ao_edital(self):
        self.client.login(username='alu_prop', password='x')
        response = self.client.post(self.url, {
            'titulo': 'Estudo de fenômenos térmicos',
            'resumo': 'Resumo do estudo.',
        })
        self.assertEqual(response.status_code, 302)
        proposta = Proposta.objects.get(titulo='Estudo de fenômenos térmicos')
        self.assertEqual(proposta.edital, self.edital)
        self.assertEqual(proposta.status, 'submetida')
        self.assertEqual(proposta.submetido_por, self.aluno.perfil.pessoa)

    def test_docente_submete_proposta(self):
        self.client.login(username='doc_prop', password='x')
        response = self.client.post(self.url, {'titulo': 'Proposta do docente'})
        self.assertEqual(response.status_code, 302)
        proposta = Proposta.objects.get(titulo='Proposta do docente')
        self.assertEqual(proposta.submetido_por, self.docente.perfil.pessoa)

    def test_tecnico_nao_submete_proposta(self):
        """Técnico+ gerencia o processo, não submete (403)."""
        self.client.login(username='tec_prop', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_submissao_bloqueada_em_edital_rascunho(self):
        rascunho = _criar_edital(codigo='RASCUNHO-01', status='rascunho')
        self.client.login(username='alu_prop', password='x')
        response = self.client.post(
            reverse('proposta_nova', kwargs={'pk': rascunho.pk}),
            {'titulo': 'Proposta a rascunho'},
            follow=True,
        )
        self.assertContains(response, 'não está aberto para submissões')
        self.assertFalse(Proposta.objects.filter(titulo='Proposta a rascunho').exists())

    def test_submissao_bloqueada_em_edital_aprovado_nao_iniciado(self):
        """Edital aprovado (validado) não recebe propostas até o iniciar."""
        aprovado = _criar_edital(codigo='APROVADO-01', status='aprovado')
        self.client.login(username='alu_prop', password='x')
        response = self.client.post(
            reverse('proposta_nova', kwargs={'pk': aprovado.pk}),
            {'titulo': 'Proposta antes da execução'},
            follow=True,
        )
        self.assertContains(response, 'não está aberto para submissões')
        self.assertFalse(
            Proposta.objects.filter(titulo='Proposta antes da execução').exists(),
        )

    def test_submissao_liberada_apos_tecnico_iniciar_execucao(self):
        """Aprovado → técnico inicia → a submissão passa a ser aceita."""
        aprovado = _criar_edital(codigo='INICIAR-01', status='aprovado')
        self.client.login(username='alu_prop', password='x')
        url = reverse('proposta_nova', kwargs={'pk': aprovado.pk})
        bloqueio = self.client.post(
            url, {'titulo': 'Antes de iniciar'}, follow=True,
        )
        self.assertContains(bloqueio, 'não está aberto para submissões')
        self.assertFalse(Proposta.objects.filter(titulo='Antes de iniciar').exists())

        self.client.login(username='tec_prop', password='x')
        iniciou = self.client.post(
            reverse('edital_acao', kwargs={'pk': aprovado.pk, 'acao': 'iniciar'}),
        )
        self.assertEqual(iniciou.status_code, 302)
        aprovado.refresh_from_db()
        self.assertEqual(aprovado.status, 'em_andamento')

        self.client.login(username='alu_prop', password='x')
        aceitou = self.client.post(url, {'titulo': 'Depois de iniciar'})
        self.assertEqual(aceitou.status_code, 302)
        self.assertTrue(Proposta.objects.filter(titulo='Depois de iniciar').exists())

    def test_submissao_bloqueada_fora_do_periodo(self):
        encerrado = _criar_edital(
            codigo='VENCIDO-01',
            data_inicio=localdate() - timedelta(days=60),
            data_fim=localdate() - timedelta(days=30),
        )
        self.client.login(username='alu_prop', password='x')
        response = self.client.post(
            reverse('proposta_nova', kwargs={'pk': encerrado.pk}),
            {'titulo': 'Proposta fora do período'},
            follow=True,
        )
        self.assertContains(response, 'não está aberto para submissões')
        self.assertFalse(Proposta.objects.filter(titulo='Proposta fora do período').exists())

    def test_submissao_sem_pessoa_vinculada_e_bloqueada(self):
        _criar_usuario('alu_sem_pessoa', Perfil.PERFIL_ALUNO, com_pessoa=False)
        self.client.login(username='alu_sem_pessoa', password='x')
        response = self.client.post(self.url, {'titulo': 'Proposta órfã'}, follow=True)
        self.assertContains(response, 'não está vinculado a uma Pessoa')
        self.assertFalse(Proposta.objects.filter(titulo='Proposta órfã').exists())

    def test_botao_submeter_visivel_apenas_para_submetentes(self):
        self.client.login(username='alu_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': self.edital.pk}))
        self.assertContains(response, '+ Submeter proposta')

        self.client.logout()
        self.client.login(username='tec_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': self.edital.pk}))
        self.assertNotContains(response, '+ Submeter proposta')

    def test_botao_oculto_em_edital_fechado(self):
        fechado = _criar_edital(codigo='FECHADO-01', status='encerrado')
        self.client.login(username='alu_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': fechado.pk}))
        self.assertNotContains(response, '+ Submeter proposta')


class GestaoPropostaTests(TestCase):
    """Visualização e edição de propostas submetidas."""

    def setUp(self):
        self.edital = _criar_edital()
        self.dono = _criar_usuario('alu_dono', Perfil.PERFIL_ALUNO)
        self.outro = _criar_usuario('alu_outro', Perfil.PERFIL_ALUNO)
        _criar_usuario('tec_gestao', Perfil.PERFIL_TECNICO)

        self.proposta = Proposta.objects.create(
            titulo='Proposta dona',
            resumo='Resumo da proposta dona.',
            edital=self.edital,
            submetido_por=self.dono.perfil.pessoa,
        )
        self.alheia = Proposta.objects.create(
            titulo='Proposta alheia',
            edital=self.edital,
            submetido_por=self.outro.perfil.pessoa,
        )

    def test_detalhe_dono_e_gerente_acessam_estranho_nao(self):
        self.client.login(username='alu_dono', password='x')
        url = reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.logout()
        self.client.login(username='alu_outro', password='x')
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.logout()
        self.client.login(username='tec_gestao', password='x')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_detalhe_exige_login(self):
        response = self.client.get(
            reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_dono_edita_proposta_submetida(self):
        self.client.login(username='alu_dono', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {'titulo': 'Proposta dona editada'},
        )
        self.assertEqual(response.status_code, 302)
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Proposta dona editada')

    def test_edicao_bloqueada_apos_avaliacao(self):
        """Status em avaliação congela a proposta (mensagem, sem mudança)."""
        self.proposta.status = 'em_avaliacao'
        self.proposta.save()
        self.client.login(username='alu_dono', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {'titulo': 'Tentativa de edição'},
            follow=True,
        )
        self.assertContains(response, 'não podem ser editadas')
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Proposta dona')

    def test_estranho_nao_edita_proposta_alheia(self):
        self.client.login(username='alu_outro', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {'titulo': 'Edição maliciosa'},
        )
        self.assertEqual(response.status_code, 403)
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Proposta dona')

    def test_tecnico_edita_proposta_alheia(self):
        self.client.login(username='tec_gestao', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {'titulo': 'Correção técnica'},
        )
        self.assertEqual(response.status_code, 302)
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Correção técnica')

    def test_listagem_no_edital_filtra_por_dono(self):
        """Gerente vê todas as propostas; submetente, apenas as próprias."""
        url = reverse('edital_detalhe', kwargs={'pk': self.edital.pk})

        self.client.login(username='tec_gestao', password='x')
        response = self.client.get(url)
        self.assertContains(response, 'Proposta dona')
        self.assertContains(response, 'Proposta alheia')

        self.client.logout()
        self.client.login(username='alu_dono', password='x')
        response = self.client.get(url)
        self.assertContains(response, 'Proposta dona')
        self.assertNotContains(response, 'Proposta alheia')
