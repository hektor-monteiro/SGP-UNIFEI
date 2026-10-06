"""Testes do módulo de Bolsas (views, permissões e regras de negócio)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto

from apps.bolsas.models import Bolsa, ModalidadeBolsa


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _criar_modalidade():
    modalidade, _ = ModalidadeBolsa.objects.get_or_create(
        sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
    )
    return modalidade


def _dados_bolsa(aluno, modalidade, projeto, **extras):
    dados = {
        'aluno': aluno.pk,
        'modalidade': modalidade.pk,
        'projeto': projeto.pk,
        'data_inicio': '2026-03-01',
        'data_fim': '2026-11-30',
        'status': 'ativa',
    }
    dados.update(extras)
    return dados


class BolsaAcessoTests(TestCase):
    """Testes de acesso às views de bolsas."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade = _criar_modalidade()
        self.docente = Pessoa.objects.create(
            nome='Docente Orientador', email='ori@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.docente_alheio = Pessoa.objects.create(
            nome='Docente Alheio', email='alheio@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno Participante', email='part@alunos.edu.br', tipo='aluno',
            matricula='20260001', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno Outro Projeto', email='outro@alunos.edu.br', tipo='aluno',
            matricula='20260002', instituicao=inst,
        )
        self.aluno3 = Pessoa.objects.create(
            nome='Aluno Sem Bolsa', email='sembolsa@alunos.edu.br', tipo='aluno',
            matricula='20260003', instituicao=inst,
        )
        self.projeto_meu = Projeto.objects.create(
            codigo='PVDIM-2026', titulo='Projeto do orientador',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.projeto_alheio = Projeto.objects.create(
            codigo='PVDIA-2026', titulo='Projeto de outro docente',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente_alheio, instituicao=inst,
        )
        self.bolsa_minha = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.bolsa_alheia = Bolsa.objects.create(
            projeto=self.projeto_alheio, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.user_docente = _criar_usuario('doc_bolsa', Perfil.PERFIL_DOCENTE, self.docente)
        self.user_aluno = _criar_usuario('alu_bolsa', Perfil.PERFIL_ALUNO, self.aluno1)
        self.user_tecnico = _criar_usuario('tec_bolsa', Perfil.PERFIL_TECNICO)

    def test_lista_exige_login(self):
        response = self.client.get(reverse('bolsas_lista'))
        self.assertEqual(response.status_code, 302)

    def test_aluno_ve_apenas_as_proprias(self):
        self.client.login(username='alu_bolsa', password='x')
        response = self.client.get(reverse('bolsas_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aluno Participante')
        self.assertNotContains(response, 'Aluno Outro Projeto')
        self.assertNotContains(response, '+ Nova bolsa')

    def test_aluno_detalhe_alheio_e_403(self):
        self.client.login(username='alu_bolsa', password='x')
        response = self.client.get(
            reverse('bolsa_detalhe', kwargs={'pk': self.bolsa_alheia.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_aluno_detalhe_propria(self):
        self.client.login(username='alu_bolsa', password='x')
        response = self.client.get(
            reverse('bolsa_detalhe', kwargs={'pk': self.bolsa_minha.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aluno Participante')

    def test_aluno_nao_cria_nem_edita(self):
        self.client.login(username='alu_bolsa', password='x')
        self.assertEqual(
            self.client.get(reverse('bolsa_nova')).status_code, 403,
        )
        self.assertEqual(
            self.client.get(
                reverse('bolsa_editar', kwargs={'pk': self.bolsa_minha.pk})
            ).status_code,
            403,
        )

    def test_docente_lista_mostra_apenas_edicao_dos_seus(self):
        """Docente edita só as bolsas de projetos que coordena."""
        self.client.login(username='doc_bolsa', password='x')
        response = self.client.get(reverse('bolsas_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Editar', count=1)
        self.assertContains(response, 'Ver', count=1)

    def test_docente_nao_edita_bolsa_de_projeto_alheio(self):
        self.client.login(username='doc_bolsa', password='x')
        response = self.client.get(
            reverse('bolsa_editar', kwargs={'pk': self.bolsa_alheia.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_tecnico_edita_qualquer_bolsa(self):
        self.client.login(username='tec_bolsa', password='x')
        response = self.client.get(
            reverse('bolsa_editar', kwargs={'pk': self.bolsa_alheia.pk})
        )
        self.assertEqual(response.status_code, 200)

    def test_tecnico_cria_bolsa_manual(self):
        """Bolsa avulsa (fora do fluxo de cotas) segue disponível p/ téc+ (§3.5)."""
        self.client.login(username='tec_bolsa', password='x')
        response = self.client.post(
            reverse('bolsa_nova'),
            _dados_bolsa(self.aluno3, self.modalidade, self.projeto_meu),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Bolsa.objects.filter(aluno=self.aluno3, projeto=self.projeto_meu).exists(),
        )

    def test_docente_nao_cria_bolsa(self):
        """Docente não cria bolsa: ele indica o aluno; o técnico implementa."""
        self.client.login(username='doc_bolsa', password='x')
        self.assertEqual(self.client.get(reverse('bolsa_nova')).status_code, 403)
        response = self.client.post(
            reverse('bolsa_nova'),
            _dados_bolsa(self.aluno3, self.modalidade, self.projeto_meu),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Bolsa.objects.filter(aluno=self.aluno3).exists())


class RegraNegocioBolsaTests(TestCase):
    """Regras de negócio do formulário de bolsa."""

    def setUp(self):
        self.docente = Pessoa.objects.create(
            nome='Docente Regra', email='regra@unifei.edu.br', tipo='docente',
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Regra', email='regra@alunos.edu.br', tipo='aluno',
            matricula='20269999',
        )
        self.modalidade = _criar_modalidade()
        self.projeto = Projeto.objects.create(
            codigo='PVDIR-2026', titulo='Projeto regras',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente,
        )
        self.user = _criar_usuario('tec_regra', Perfil.PERFIL_TECNICO)

    def test_segunda_bolsa_ativa_e_rejeitada(self):
        """Aluno já com bolsa ativa não pode receber outra ativa."""
        Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.client.login(username='tec_regra', password='x')
        response = self.client.post(reverse('bolsa_nova'), _dados_bolsa(
            self.aluno, self.modalidade, self.projeto, data_inicio='2026-08-01',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui bolsa ativa')
        self.assertEqual(Bolsa.objects.filter(aluno=self.aluno).count(), 1)

    def test_bolsa_encerrada_nao_bloqueia_nova_ativa(self):
        """A regra vale apenas para bolsas com status 'ativa'."""
        Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno, modalidade=self.modalidade,
            data_inicio=date(2025, 3, 1), data_fim=date(2025, 11, 30),
            status='encerrada',
        )
        self.client.login(username='tec_regra', password='x')
        response = self.client.post(
            reverse('bolsa_nova'),
            _dados_bolsa(self.aluno, self.modalidade, self.projeto),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Bolsa.objects.filter(aluno=self.aluno, status='ativa').count(), 1,
        )

    def test_data_fim_menor_que_inicio_e_rejeitada(self):
        self.client.login(username='tec_regra', password='x')
        response = self.client.post(reverse('bolsa_nova'), _dados_bolsa(
            self.aluno, self.modalidade, self.projeto,
            data_inicio='2026-11-30', data_fim='2026-03-01',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'posterior')
        self.assertFalse(Bolsa.objects.exists())

    def test_aluno_do_formulario_deve_ser_tipo_aluno(self):
        """Docente (tipo 'docente') não pode ser selecionado como aluno da bolsa."""
        self.client.login(username='tec_regra', password='x')
        response = self.client.post(
            reverse('bolsa_nova'),
            _dados_bolsa(self.docente, self.modalidade, self.projeto),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'escolha válida')
        self.assertFalse(Bolsa.objects.exists())


class ModalidadeTests(TestCase):
    """Gestão de modalidades: apenas técnico+ (requisito §3.2, não hardcoded)."""

    def setUp(self):
        _criar_usuario('alu_mod', Perfil.PERFIL_ALUNO)
        _criar_usuario('doc_mod', Perfil.PERFIL_DOCENTE)
        _criar_usuario('tec_mod', Perfil.PERFIL_TECNICO)

    def test_aluno_e_docente_bloqueados(self):
        for username in ('alu_mod', 'doc_mod'):
            self.client.login(username=username, password='x')
            self.assertEqual(
                self.client.get(reverse('modalidades_lista')).status_code, 403,
            )
            self.client.logout()

    def test_tecnico_lista_modalidades(self):
        self.client.login(username='tec_mod', password='x')
        response = self.client.get(reverse('modalidades_lista'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '+ Nova modalidade')

    def test_tecnico_cria_modalidade(self):
        self.client.login(username='tec_mod', password='x')
        response = self.client.post(reverse('modalidade_nova'), {
            'sigla': 'PIBITI',
            'nome': 'Tecnologia da Informação',
            'descricao': '',
            'ativo': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ModalidadeBolsa.objects.filter(sigla='PIBITI').exists())

    def test_modalidade_nova_aparece_no_form_de_bolsa(self):
        """Modalidade criada pelo técnico fica disponível sem mudar código."""
        self.client.login(username='tec_mod', password='x')
        self.client.post(reverse('modalidade_nova'), {
            'sigla': 'PIVIC',
            'nome': 'Voluntária',
            'descricao': '',
            'ativo': 'on',
        })
        response = self.client.get(reverse('bolsa_nova'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'PIVIC')
