"""Testes do módulo de Relatórios do aluno (views, permissões e regras)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Instituicao, Perfil
from apps.projetos.models import Pessoa, Projeto

from apps.bolsas.models import Bolsa, ModalidadeBolsa
from apps.equipes.models import MembroEquipe
from apps.relatorios.models import Relatorio
from sgp.tests.arquivos_teste import MediaTemporariaMixin, anexar_pdf


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _dados_relatorio(bolsa, **extras):
    dados = {
        'bolsa': bolsa.pk,
        'tipo': 'parcial',
        'titulo': 'Relatório parcial de pesquisa',
        'resumo': 'Resumo do relatório para a busca do sistema.',
        'periodo_inicio': '2026-03-01',
        'periodo_fim': '2026-11-30',
    }
    dados.update(extras)
    return dados


class RelatorioAcessoTests(MediaTemporariaMixin, TestCase):
    """Testes de acesso às views de relatórios."""

    def setUp(self):
        super().setUp()
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Rel', email='reldoc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.docente_alheio = Pessoa.objects.create(
            nome='Docente Outro', email='outrodoc2@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno Rel', email='relalu@alunos.edu.br', tipo='aluno',
            matricula='20260031', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno de Outro', email='outro2@alunos.edu.br', tipo='aluno',
            matricula='20260032', instituicao=inst,
        )
        self.projeto_meu = Projeto.objects.create(
            codigo='PVDIR-2026', titulo='Projeto com relatório',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.projeto_alheio = Projeto.objects.create(
            codigo='PVDIO2-2026', titulo='Projeto alheio',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente_alheio, instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.bolsa_sem_relatorio = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2025, 3, 1), data_fim=date(2025, 11, 30),
            status='encerrada',
        )
        self.bolsa_alheia = Bolsa.objects.create(
            projeto=self.projeto_alheio, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        # Rascunho do aluno1 (parcial) e final reprovado com avaliação anterior
        self.rel_rascunho = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno1, tipo='parcial',
            titulo='Relatório parcial do aluno',
        )
        self.rel_reprovado = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno1, tipo='final',
            titulo='Relatório final do aluno', status='reprovado',
            nota=Decimal('4.00'), observacoes='Refaça as análises.',
            avaliado_por=self.docente,
        )
        # Submissão (e re-submissão) exige o documento em PDF anexado
        anexar_pdf(self.rel_rascunho, nome='rascunho.pdf')
        anexar_pdf(self.rel_reprovado, nome='reprovado.pdf')
        # Submetido do aluno2 (oriente do docente alheio)
        self.rel_submetido_alheio = Relatorio.objects.create(
            bolsa=self.bolsa_alheia, aluno=self.aluno2, tipo='final',
            titulo='Relatório final do outro aluno', status='submetido',
        )
        _criar_usuario('alu_rel', Perfil.PERFIL_ALUNO, self.aluno1)
        _criar_usuario('doc_rel', Perfil.PERFIL_DOCENTE, self.docente)
        _criar_usuario('doc_2', Perfil.PERFIL_DOCENTE, self.docente_alheio)
        _criar_usuario('tec_rel', Perfil.PERFIL_TECNICO)

    def test_lista_exige_login(self):
        self.assertEqual(self.client.get(reverse('relatorios_lista')).status_code, 302)

    def test_aluno_lista_apenas_os_proprios(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.get(reverse('relatorios_lista'))
        self.assertContains(response, 'Relatório parcial do aluno')
        self.assertContains(response, 'Relatório final do aluno')
        self.assertNotContains(response, 'Relatório final do outro aluno')
        # Tem bolsa → pode criar
        self.assertContains(response, '+ Novo relatório')

    def test_aluno_detalhe_alheio_e_403(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.get(
            reverse('relatorio_detalhe', kwargs={'pk': self.rel_submetido_alheio.pk})
        )
        self.assertEqual(response.status_code, 403)

    def test_aluno_detalhe_mostra_vinculos(self):
        """O detalhe exibe a associação dupla: bolsa e projeto do docente."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.get(
            reverse('relatorio_detalhe', kwargs={'pk': self.rel_rascunho.pk})
        )
        self.assertContains(
            response, reverse('bolsa_detalhe', kwargs={'pk': self.bolsa.pk}),
        )
        self.assertContains(
            response, reverse('projeto_detalhe', kwargs={'pk': self.projeto_meu.pk}),
        )

    def test_aluno_cria_relatorio_com_aluno_derivado_da_bolsa(self):
        """Aluno cria relatório na própria bolsa; aluno deriva da bolsa."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_novo'),
            _dados_relatorio(self.bolsa_sem_relatorio, tipo='final'),
        )
        self.assertEqual(response.status_code, 302)
        relatorio = Relatorio.objects.get(bolsa=self.bolsa_sem_relatorio)
        self.assertEqual(relatorio.aluno, self.aluno1)
        self.assertEqual(relatorio.status, 'rascunho')

    def test_aluno_nao_cria_relatorio_para_bolsa_de_outro(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_novo'),
            _dados_relatorio(self.bolsa_alheia),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'escolha válida')
        self.assertEqual(
            Relatorio.objects.filter(bolsa=self.bolsa_alheia).count(), 1,
        )

    def test_relatorio_final_duplicado_e_rejeitado(self):
        """Apenas um final por bolsa: repetir cai no clean() com mensagem."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_novo'),
            _dados_relatorio(self.bolsa, tipo='final'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já possui relatório final')

    def test_parcial_repetido_e_permitido(self):
        """Parciais podem se repetir (um por período)."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_novo'),
            _dados_relatorio(self.bolsa, titulo='Segundo parcial'),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Relatorio.objects.filter(
                bolsa=self.bolsa, tipo='parcial', titulo='Segundo parcial',
            ).exists(),
        )

    def test_periodo_invalido_e_rejeitado(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_novo'),
            _dados_relatorio(
                self.bolsa_sem_relatorio, tipo='final',
                periodo_inicio='2026-11-30', periodo_fim='2026-03-01',
            ),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não pode ser posterior')

    def test_aluno_edita_apenas_rascunho_ou_reprovado(self):
        self.client.login(username='alu_rel', password='x')
        # Rascunho: edita; reprovado: edita (para corrigir e re-submeter)
        self.assertEqual(
            self.client.get(
                reverse('relatorio_editar', kwargs={'pk': self.rel_rascunho.pk})
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(
                reverse('relatorio_editar', kwargs={'pk': self.rel_reprovado.pk})
            ).status_code,
            200,
        )
        # Submetido: bloqueado
        self.rel_rascunho.status = 'submetido'
        self.rel_rascunho.save()
        self.assertEqual(
            self.client.get(
                reverse('relatorio_editar', kwargs={'pk': self.rel_rascunho.pk})
            ).status_code,
            403,
        )

    def test_aluno_submete_relatorio(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_submeter', kwargs={'pk': self.rel_rascunho.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'submetido')
        self.assertIsNotNone(self.rel_rascunho.data_submissao)

    def test_submeter_get_e_405(self):
        """A submissão é somente POST."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.get(
            reverse('relatorio_submeter', kwargs={'pk': self.rel_rascunho.pk}),
        )
        self.assertEqual(response.status_code, 405)

    def test_aluno_nao_submete_relatorio_alheio(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_submeter', kwargs={'pk': self.rel_submetido_alheio.pk}),
        )
        self.assertEqual(response.status_code, 403)

    def test_resubmissao_limpa_avaliacao_anterior(self):
        """Reprovação → aluno corrige → submeter limpa nota/observações."""
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_submeter', kwargs={'pk': self.rel_reprovado.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.rel_reprovado.refresh_from_db()
        self.assertEqual(self.rel_reprovado.status, 'submetido')
        self.assertIsNone(self.rel_reprovado.nota)
        self.assertEqual(self.rel_reprovado.observacoes, '')
        self.assertIsNone(self.rel_reprovado.avaliado_por)
        self.assertIsNone(self.rel_reprovado.data_avaliacao)

    def test_orientador_avalia_aprova_com_carimbo(self):
        """Orientador avalia nota alta → aprovado, com carimbos."""
        self.rel_rascunho.status = 'submetido'
        self.rel_rascunho.save()
        self.client.login(username='doc_rel', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '8.00', 'observacoes': 'Bom trabalho.'},
        )
        self.assertEqual(response.status_code, 302)
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'aprovado')
        self.assertEqual(self.rel_rascunho.nota, Decimal('8.00'))
        self.assertEqual(self.rel_rascunho.avaliado_por, self.docente)
        self.assertIsNotNone(self.rel_rascunho.data_avaliacao)
        self.assertEqual(self.rel_rascunho.observacoes, 'Bom trabalho.')

    def test_aprovacao_na_nota_minima(self):
        """Nota exatamente na mínima (6,00) aprova."""
        self.rel_rascunho.status = 'submetido'
        self.rel_rascunho.save()
        self.client.login(username='doc_rel', password='x')
        self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '6.00', 'observacoes': ''},
        )
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'aprovado')

    def test_nota_abaixo_da_minima_reprova(self):
        self.rel_rascunho.status = 'submetido'
        self.rel_rascunho.save()
        self.client.login(username='doc_rel', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '5.50', 'observacoes': 'Abaixo do esperado.'},
        )
        self.assertEqual(response.status_code, 302)
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'reprovado')
        self.assertEqual(self.rel_rascunho.nota, Decimal('5.50'))

    def test_nota_fora_do_intervalo_e_rejeitada(self):
        self.rel_rascunho.status = 'submetido'
        self.rel_rascunho.save()
        self.client.login(username='doc_rel', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '11', 'observacoes': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('nota', response.context['form'].errors)
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'submetido')  # intacto

    def test_docente_alheio_nao_avalia(self):
        """doc_2 é orientador de OUTRO aluno; não avalia o relatório de alheio."""
        self.client.login(username='doc_2', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '9.00', 'observacoes': ''},
        )
        self.assertEqual(response.status_code, 403)

    def test_aluno_nao_avalia(self):
        self.client.login(username='alu_rel', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
            {'nota': '9.00', 'observacoes': ''},
        )
        self.assertEqual(response.status_code, 403)

    def test_avaliar_relatorio_nao_submetido_redireciona(self):
        """Apenas submetidos podem ser avaliados: redireciona com aviso."""
        self.client.login(username='doc_rel', password='x')
        response = self.client.get(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_rascunho.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.rel_rascunho.refresh_from_db()
        self.assertEqual(self.rel_rascunho.status, 'rascunho')

    def test_tecnico_avalia_qualquer_relatorio(self):
        """Técnico+ avalia relatório de qualquer bolsa (gerência DIP)."""
        self.client.login(username='tec_rel', password='x')
        response = self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_submetido_alheio.pk}),
            {'nota': '9.00', 'observacoes': 'De acordo.'},
        )
        self.assertEqual(response.status_code, 302)
        self.rel_submetido_alheio.refresh_from_db()
        self.assertEqual(self.rel_submetido_alheio.status, 'aprovado')

    def test_lista_filtros_por_tipo_e_status(self):
        self.client.login(username='tec_rel', password='x')
        response = self.client.get(
            reverse('relatorios_lista'), {'tipo': 'final', 'status': 'submetido'},
        )
        self.assertContains(response, 'Relatório final do outro aluno')
        self.assertNotContains(response, 'Relatório parcial do aluno')


class IntegracoesTests(TestCase):
    """Integrações: painel (aluno/orientador/técnico) e página da bolsa."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Int', email='int2@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Int', email='int2@alunos.edu.br', tipo='aluno',
            matricula='20260041', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PVDII2-2026', titulo='Projeto integração relatórios',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno, modalidade=modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.rel_submetido = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno, tipo='final',
            titulo='Relatório integrado', status='submetido',
        )
        _criar_usuario('alu_int2', Perfil.PERFIL_ALUNO, self.aluno)
        _criar_usuario('doc_int2', Perfil.PERFIL_DOCENTE, self.docente)
        _criar_usuario('tec_int2', Perfil.PERFIL_TECNICO)
        # Docente não coordenador (não avalia os relatórios deste projeto)
        docente_visitante = Pessoa.objects.create(
            nome='Docente Visitante2', email='visit2@unifei.edu.br', tipo='docente',
        )
        _criar_usuario('doc_vis2', Perfil.PERFIL_DOCENTE, docente_visitante)

    def test_painel_aluno_lista_seus_relatorios(self):
        self.client.login(username='alu_int2', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Seus relatórios')
        self.assertContains(response, 'Relatório integrado')
        self.assertContains(
            response, reverse('relatorio_detalhe', kwargs={'pk': self.rel_submetido.pk}),
        )
        # Aluno não avalia: a seção de avaliação não aparece
        self.assertNotContains(response, 'Relatórios a avaliar')

    def test_painel_orientador_mostra_relatorios_a_avaliar(self):
        self.client.login(username='doc_int2', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Relatórios a avaliar (1)')
        self.assertContains(
            response, reverse('relatorio_avaliar', kwargs={'pk': self.rel_submetido.pk}),
        )

    def test_painel_tecnico_lista_qualquer(self):
        self.client.login(username='tec_int2', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Relatórios a avaliar (1)')

    def test_painel_docente_nao_coordenador_sem_lista(self):
        self.client.login(username='doc_vis2', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Relatórios a avaliar')

    def test_bolsa_detalhe_mostra_relatorios(self):
        """A página da bolsa exibe os relatórios vinculados."""
        self.client.login(username='doc_int2', password='x')
        response = self.client.get(
            reverse('bolsa_detalhe', kwargs={'pk': self.bolsa.pk}),
        )
        self.assertContains(
            response, reverse('relatorio_detalhe', kwargs={'pk': self.rel_submetido.pk}),
        )
        self.assertContains(response, 'Submetido')


class CoorientadorAvaliacaoTests(TestCase):
    """Avaliação por co-orientador: vínculo ativo em MembroEquipe (§3.10)."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(
            sigla='IMC', defaults={'nome': 'IMC'},
        )
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.coordenador = Pessoa.objects.create(
            nome='Coordenador CO', email='coordco@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.coorientador = Pessoa.objects.create(
            nome='Docente Coorientador', email='coorient@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.coorientador_inativo = Pessoa.objects.create(
            nome='Docente Ex-Coorientador', email='excoorient@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.docente_alheio = Pessoa.objects.create(
            nome='Docente Sem Vínculo CO', email='semvinc@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.aluno = Pessoa.objects.create(
            nome='Aluno Coorientação', email='aluco@alunos.edu.br',
            tipo='aluno', matricula='20260091', instituicao=inst,
        )
        self.projeto = Projeto.objects.create(
            codigo='PVCO-2026', titulo='Projeto com coorientação',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.coordenador, instituicao=inst, status='vigente',
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno,
            modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.rel_submetido = Relatorio.objects.create(
            bolsa=self.bolsa, aluno=self.aluno, tipo='parcial',
            titulo='Relatório do coorientando', status='submetido',
        )
        MembroEquipe.objects.create(
            projeto=self.projeto, pessoa=self.coorientador,
            funcao='coorientador', data_entrada=date(2026, 3, 1),
        )
        MembroEquipe.objects.create(
            projeto=self.projeto, pessoa=self.coorientador_inativo,
            funcao='coorientador', data_entrada=date(2026, 3, 1),
            data_saida=date(2026, 6, 1), ativo=False,
        )
        _criar_usuario('doc_co', Perfil.PERFIL_DOCENTE, self.coorientador)
        _criar_usuario(
            'doc_co_out', Perfil.PERFIL_DOCENTE, self.coorientador_inativo,
        )
        _criar_usuario('doc_co_alheio', Perfil.PERFIL_DOCENTE, self.docente_alheio)
        _criar_usuario('doc_co_coord', Perfil.PERFIL_DOCENTE, self.coordenador)

    def _avaliar(self, username, nota='8.00'):
        self.client.login(username=username, password='x')
        return self.client.post(
            reverse('relatorio_avaliar', kwargs={'pk': self.rel_submetido.pk}),
            {'nota': nota, 'observacoes': 'Avaliado como co-orientador.'},
        )

    def test_coorientador_ativo_avalia(self):
        response = self._avaliar('doc_co')
        self.assertEqual(response.status_code, 302)
        self.rel_submetido.refresh_from_db()
        self.assertEqual(self.rel_submetido.status, 'aprovado')
        self.assertEqual(self.rel_submetido.avaliado_por, self.coorientador)

    def test_coorientador_inativo_nao_avalia(self):
        response = self._avaliar('doc_co_out', nota='1.00')
        self.assertEqual(response.status_code, 403)
        self.rel_submetido.refresh_from_db()
        self.assertEqual(self.rel_submetido.status, 'submetido')

    def test_docente_sem_vinculo_nao_avalia(self):
        response = self._avaliar('doc_co_alheio', nota='1.00')
        self.assertEqual(response.status_code, 403)
        self.rel_submetido.refresh_from_db()
        self.assertEqual(self.rel_submetido.status, 'submetido')

    def test_painel_mostra_relatorio_para_coorientador(self):
        self.client.login(username='doc_co', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Relatório do coorientando')
        # Sem vínculo não vê
        self.client.logout()
        self.client.login(username='doc_co_alheio', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'Relatório do coorientando')

    def test_lista_marca_como_avaliavel_para_coorientador(self):
        self.client.login(username='doc_co', password='x')
        response = self.client.get(reverse('relatorios_lista'))
        self.assertIn(self.rel_submetido.pk, response.context['avaliaveis'])
        self.client.logout()
        self.client.login(username='doc_co_out', password='x')
        response = self.client.get(reverse('relatorios_lista'))
        self.assertNotIn(self.rel_submetido.pk, response.context['avaliaveis'])
