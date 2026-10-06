"""Testes de submissão e gestão de propostas a editais."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localdate

from apps.core.models import Perfil
from apps.editais.models import Edital
from apps.projetos.models import Pessoa, Projeto, Proposta


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
        self.projeto = Projeto.objects.create(
            codigo='PROJ-SUB-01',
            titulo='Projeto de submissão de teste',
            data_registro=localdate(),
            data_inicio=localdate() - timedelta(days=10),
            coordenador=self.docente.perfil.pessoa,
        )
        self.url = reverse('proposta_nova', kwargs={'pk': self.edital.pk})

    def test_aluno_nao_submete_proposta(self):
        """Aluno não submete: ele é indicado pelo docente (§3.5)."""
        self.client.login(username='alu_prop', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)
        response = self.client.post(self.url, {'titulo': 'Proposta do aluno'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Proposta.objects.filter(titulo='Proposta do aluno').exists())

    def test_docente_submete_proposta_com_cotas(self):
        self.client.login(username='doc_prop', password='x')
        response = self.client.post(self.url, {
            'projeto': str(self.projeto.pk),
            'titulo': 'Proposta do docente',
            'cotas': 3,
            'resumo': 'Resumo da proposta.',
        })
        self.assertEqual(response.status_code, 302)
        proposta = Proposta.objects.get(titulo='Proposta do docente')
        self.assertEqual(proposta.submetido_por, self.docente.perfil.pessoa)
        self.assertEqual(proposta.projeto, self.projeto)
        self.assertEqual(proposta.cotas, 3)
        self.assertEqual(proposta.status, 'submetida')

    def test_submissao_exige_projeto_do_docente(self):
        """Sem projeto ou com projeto inválido → volta ao form com erro."""
        self.client.login(username='doc_prop', password='x')
        response = self.client.post(self.url, {'titulo': 'Sem projeto'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'obrigat')
        self.assertFalse(Proposta.objects.filter(titulo='Sem projeto').exists())

        _criar_usuario('doc_sem_proj', Perfil.PERFIL_DOCENTE)
        self.client.login(username='doc_sem_proj', password='x')
        response = self.client.post(self.url, {
            'titulo': 'Projeto alheio',
            'projeto': str(self.projeto.pk),
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'escolha válida')
        self.assertFalse(Proposta.objects.filter(titulo='Projeto alheio').exists())

    def test_tecnico_nao_submete_proposta(self):
        """Técnico+ gerencia o processo, não submete (403)."""
        self.client.login(username='tec_prop', password='x')
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_submissao_bloqueada_em_edital_rascunho(self):
        rascunho = _criar_edital(codigo='RASCUNHO-01', status='rascunho')
        self.client.login(username='doc_prop', password='x')
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
        self.client.login(username='doc_prop', password='x')
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
        self.client.login(username='doc_prop', password='x')
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

        self.client.login(username='doc_prop', password='x')
        aceitou = self.client.post(url, {
            'projeto': str(self.projeto.pk),
            'titulo': 'Depois de iniciar',
            'cotas': 1,
        })
        self.assertEqual(aceitou.status_code, 302)
        self.assertTrue(Proposta.objects.filter(titulo='Depois de iniciar').exists())

    def test_submissao_bloqueada_fora_do_periodo(self):
        encerrado = _criar_edital(
            codigo='VENCIDO-01',
            data_inicio=localdate() - timedelta(days=60),
            data_fim=localdate() - timedelta(days=30),
        )
        self.client.login(username='doc_prop', password='x')
        response = self.client.post(
            reverse('proposta_nova', kwargs={'pk': encerrado.pk}),
            {'titulo': 'Proposta fora do período'},
            follow=True,
        )
        self.assertContains(response, 'não está aberto para submissões')
        self.assertFalse(Proposta.objects.filter(titulo='Proposta fora do período').exists())

    def test_submissao_sem_pessoa_vinculada_e_bloqueada(self):
        _criar_usuario('doc_sem_pessoa', Perfil.PERFIL_DOCENTE, com_pessoa=False)
        self.client.login(username='doc_sem_pessoa', password='x')
        response = self.client.post(self.url, {'titulo': 'Proposta órfã'}, follow=True)
        self.assertContains(response, 'não está vinculado a uma Pessoa')
        self.assertFalse(Proposta.objects.filter(titulo='Proposta órfã').exists())

    def test_botao_submeter_visivel_apenas_para_docente(self):
        """Só docente vê o botão: aluno é indicado, técnico gerencia."""
        self.client.login(username='doc_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': self.edital.pk}))
        self.assertContains(response, '+ Submeter proposta')

        self.client.logout()
        self.client.login(username='alu_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': self.edital.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '+ Submeter proposta')

        self.client.logout()
        self.client.login(username='tec_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': self.edital.pk}))
        self.assertNotContains(response, '+ Submeter proposta')

    def test_edital_fechado_e_invisivel_para_aluno(self):
        """Abaixo de técnicos, edital fora de 'em andamento' não abre (§3.1)."""
        fechado = _criar_edital(codigo='FECHADO-01', status='encerrado')
        self.client.login(username='alu_prop', password='x')
        response = self.client.get(reverse('edital_detalhe', kwargs={'pk': fechado.pk}))
        self.assertEqual(response.status_code, 403)


class GestaoPropostaTests(TestCase):
    """Visualização e edição de propostas submetidas."""

    def setUp(self):
        self.edital = _criar_edital()
        self.dono = _criar_usuario('doc_dono', Perfil.PERFIL_DOCENTE)
        self.outro = _criar_usuario('doc_outro', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_gestao', Perfil.PERFIL_TECNICO)
        self.projeto = Projeto.objects.create(
            codigo='PROJ-GEST-01',
            titulo='Projeto de gestão de teste',
            data_registro=localdate(),
            data_inicio=localdate() - timedelta(days=10),
            coordenador=self.dono.perfil.pessoa,
        )

        self.proposta = Proposta.objects.create(
            titulo='Proposta dona',
            resumo='Resumo da proposta dona.',
            edital=self.edital,
            projeto=self.projeto,
            cotas=2,
            submetido_por=self.dono.perfil.pessoa,
        )
        self.alheia = Proposta.objects.create(
            titulo='Proposta alheia',
            edital=self.edital,
            submetido_por=self.outro.perfil.pessoa,
        )

    def test_detalhe_dono_e_gerente_acessam_estranho_nao(self):
        self.client.login(username='doc_dono', password='x')
        url = reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        self.assertEqual(self.client.get(url).status_code, 200)

        self.client.logout()
        self.client.login(username='doc_outro', password='x')
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.logout()
        self.client.login(username='tec_gestao', password='x')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_detalhe_exige_login(self):
        response = self.client.get(
            reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk})
        )
        self.assertEqual(response.status_code, 302)

    def test_edital_oculto_aparece_como_texto_na_proposta(self):
        """Submetente vê o edital como texto (sem link) quando oculto (§3.1)."""
        self.edital.status = 'encerrado'
        self.edital.save()
        self.client.login(username='doc_dono', password='x')
        response = self.client.get(
            reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.edital.codigo)
        self.assertNotContains(
            response,
            reverse('edital_detalhe', kwargs={'pk': self.edital.pk}),
        )
        self.assertNotContains(response, '← Voltar ao edital')

    def test_edital_visivel_continua_linkado_na_proposta(self):
        """Com o edital em andamento, o link segue normal (submetente)."""
        self.client.login(username='doc_dono', password='x')
        response = self.client.get(
            reverse('proposta_detalhe', kwargs={'pk': self.proposta.pk}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            reverse('edital_detalhe', kwargs={'pk': self.edital.pk}),
        )

    def test_dono_edita_proposta_submetida(self):
        self.client.login(username='doc_dono', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {
                'titulo': 'Proposta dona editada',
                'projeto': str(self.projeto.pk),
                'cotas': 3,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Proposta dona editada')
        self.assertEqual(self.proposta.cotas, 3)

    def test_edicao_bloqueada_apos_avaliacao(self):
        """Status em avaliação congela a proposta (mensagem, sem mudança)."""
        self.proposta.status = 'em_avaliacao'
        self.proposta.save()
        self.client.login(username='doc_dono', password='x')
        response = self.client.post(
            reverse('proposta_editar', kwargs={'pk': self.proposta.pk}),
            {'titulo': 'Tentativa de edição'},
            follow=True,
        )
        self.assertContains(response, 'não podem ser editadas')
        self.proposta.refresh_from_db()
        self.assertEqual(self.proposta.titulo, 'Proposta dona')

    def test_estranho_nao_edita_proposta_alheia(self):
        self.client.login(username='doc_outro', password='x')
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
            {
                'titulo': 'Correção técnica',
                'projeto': str(self.projeto.pk),
                'cotas': 2,
            },
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
        self.client.login(username='doc_dono', password='x')
        response = self.client.get(url)
        self.assertContains(response, 'Proposta dona')
        self.assertNotContains(response, 'Proposta alheia')
