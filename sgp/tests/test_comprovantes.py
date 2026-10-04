"""Testes do módulo de Comprovantes (emissão, permissões e verificação)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.comprovantes.models import Comprovante
from apps.core.models import Instituicao, Perfil
from apps.editais.models import Avaliacao
from apps.equipes.models import MembroEquipe
from apps.projetos.models import Pessoa, Projeto, Proposta
from apps.relatorios.models import Relatorio
from apps.bolsas.models import Bolsa, ModalidadeBolsa


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


class ComprovanteBase(TestCase):
    """Base com dados comuns: 2 projetos, bolsas, relatório avaliado e
    avaliação de proposta concluída."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='IMC', defaults={'nome': 'IMC'})
        self.modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        self.docente = Pessoa.objects.create(
            nome='Docente Comp', email='compdoc@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.docente_outro = Pessoa.objects.create(
            nome='Docente Outro', email='compdoc2@unifei.edu.br', tipo='docente', instituicao=inst,
        )
        self.aluno1 = Pessoa.objects.create(
            nome='Aluno Comp', email='compalu@alunos.edu.br', tipo='aluno',
            matricula='20260041', instituicao=inst,
        )
        self.aluno2 = Pessoa.objects.create(
            nome='Aluno Outro Projeto', email='compalu2@alunos.edu.br', tipo='aluno',
            matricula='20260042', instituicao=inst,
        )
        self.projeto_meu = Projeto.objects.create(
            codigo='PVCMP-2026', titulo='Projeto comprovantes',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente, instituicao=inst,
        )
        self.projeto_alheio = Projeto.objects.create(
            codigo='PVCO2-2026', titulo='Projeto alheio',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente_outro, instituicao=inst,
        )
        self.bolsa = Bolsa.objects.create(
            projeto=self.projeto_meu, aluno=self.aluno1, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.bolsa_alheia = Bolsa.objects.create(
            projeto=self.projeto_alheio, aluno=self.aluno2, modalidade=self.modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        # aluno1 é membro (discente) do projeto próprio
        MembroEquipe.objects.create(
            projeto=self.projeto_meu, pessoa=self.aluno1, funcao='discente',
            data_entrada=date(2026, 3, 1),
        )

        self.u_aluno = _criar_usuario('alu_comp', Perfil.PERFIL_ALUNO, self.aluno1)
        self.u_aluno2 = _criar_usuario('alu_comp2', Perfil.PERFIL_ALUNO, self.aluno2)
        self.u_doc = _criar_usuario('doc_comp', Perfil.PERFIL_DOCENTE, self.docente)
        self.u_doc_outro = _criar_usuario('doc_comp2', Perfil.PERFIL_DOCENTE, self.docente_outro)
        self.u_tec = _criar_usuario('tec_comp', Perfil.PERFIL_TECNICO)  # sem pessoa

        # Relatório avaliado pelo docente
        self.relatorio = Relatorio.objects.create(
            aluno=self.aluno1, bolsa=self.bolsa, tipo='final',
            titulo='Relatório final de pesquisa', conteudo='Conteúdo',
            periodo_inicio=date(2026, 3, 1), periodo_fim=date(2026, 8, 31),
            status='avaliado', nota=Decimal('7.50'),
            avaliado_por=self.docente, data_avaliacao=timezone.now(),
        )

        # Avaliação de proposta concluída pelo docente
        self.proposta = Proposta.objects.create(
            titulo='Proposta comprovável', submetido_por=self.aluno1,
        )
        self.avaliacao = Avaliacao.objects.create(
            tipo='proposta', proposta=self.proposta, avaliador=self.u_doc,
            status='concluida', nota=Decimal('8.00'),
            data_conclusao=timezone.now(),
        )


class ComprovanteAcessoTests(ComprovanteBase):
    """Acesso à lista e ao detalhe."""

    def test_lista_exige_login(self):
        resp = self.client.get(reverse('comprovantes_lista'))
        self.assertEqual(resp.status_code, 302)

    def test_aluno_lista_apenas_proprios_e_emitidos(self):
        # Comprovante de outro aluno não deve aparecer
        comp_outro = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno2, projeto=self.projeto_alheio,
            bolsa=self.bolsa_alheia, descricao='Bolsa de outro',
        )
        comp_seu = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno1, projeto=self.projeto_meu,
            bolsa=self.bolsa, descricao='Minha bolsa',
        )
        self.client.login(username='alu_comp', password='x')
        resp = self.client.get(reverse('comprovantes_lista'))
        conteudo = resp.content.decode()
        self.assertIn(comp_seu.codigo_verificacao, conteudo)
        self.assertNotIn(comp_outro.codigo_verificacao, conteudo)

    def test_detalhe_alheio_retorna_403(self):
        comp = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno2, projeto=self.projeto_alheio,
            bolsa=self.bolsa_alheia, descricao='Bolsa de outro',
        )
        self.client.login(username='alu_comp', password='x')
        resp = self.client.get(reverse('comprovante_detalhe', args=[comp.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_detalhe_dono_mostra_codigo(self):
        comp = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno1, projeto=self.projeto_meu,
            bolsa=self.bolsa, descricao='Minha bolsa',
        )
        self.client.login(username='alu_comp', password='x')
        resp = self.client.get(reverse('comprovante_detalhe', args=[comp.pk]))
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode()
        self.assertIn(comp.codigo_verificacao, conteudo)
        self.assertIn('Imprimir', conteudo)


class EmissaoBolsaTests(ComprovanteBase):
    """Comprovante de bolsa (§3.11 — aluno beneficiário / orientador)."""

    def test_aluno_emite_comprovante_da_propria_bolsa(self):
        self.client.login(username='alu_comp', password='x')
        resp = self.client.post(reverse('comprovante_emitir_bolsa'), {'bolsa': self.bolsa.pk})
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(bolsa=self.bolsa)
        self.assertEqual(comp.tipo, 'bolsa')
        self.assertEqual(comp.pessoa, self.aluno1)
        self.assertEqual(comp.emitido_por, self.u_aluno)
        self.assertEqual(comp.projeto, self.projeto_meu)
        self.assertEqual(comp.data_inicio, date(2026, 3, 1))
        self.assertEqual(comp.data_fim, date(2026, 11, 30))
        self.assertEqual(len(comp.codigo_verificacao), 16)

    def test_aluno_nao_emite_bolsa_alheia(self):
        self.client.login(username='alu_comp', password='x')
        resp = self.client.post(reverse('comprovante_emitir_bolsa'), {'bolsa': self.bolsa_alheia.pk})
        self.assertContains(resp, 'escolha válida', status_code=200)
        self.assertFalse(Comprovante.objects.filter(bolsa=self.bolsa_alheia).exists())

    def test_orientador_emite_para_orientando(self):
        self.client.login(username='doc_comp', password='x')
        resp = self.client.post(reverse('comprovante_emitir_bolsa'), {'bolsa': self.bolsa.pk})
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(bolsa=self.bolsa)
        self.assertEqual(comp.pessoa, self.aluno1)
        self.assertEqual(comp.emitido_por, self.u_doc)

    def test_docente_sem_vinculo_nao_emite(self):
        self.client.login(username='doc_comp2', password='x')
        resp = self.client.post(reverse('comprovante_emitir_bolsa'), {'bolsa': self.bolsa.pk})
        self.assertContains(resp, 'escolha válida', status_code=200)
        self.assertFalse(Comprovante.objects.filter(bolsa=self.bolsa).exists())

    def test_codigos_unicos_por_emissao(self):
        """Reemitir o mesmo objeto gera códigos diferentes (sem colisão)."""
        self.client.login(username='alu_comp', password='x')
        url = reverse('comprovante_emitir_bolsa')
        self.client.post(url, {'bolsa': self.bolsa.pk})
        self.client.post(url, {'bolsa': self.bolsa.pk})
        codigos = list(
            Comprovante.objects.filter(bolsa=self.bolsa)
            .values_list('codigo_verificacao', flat=True),
        )
        self.assertEqual(len(codigos), 2)
        self.assertEqual(len(set(codigos)), 2)


class EmissaoParticipacaoTests(ComprovanteBase):
    """Comprovante de participação em projeto (§3.11 — coordenador/membros)."""

    def test_membro_emite_participacao_propia(self):
        self.client.login(username='alu_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_participacao'), {'projeto': self.projeto_meu.pk},
        )
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(tipo='participacao_projeto', pessoa=self.aluno1)
        self.assertEqual(comp.projeto, self.projeto_meu)
        self.assertIn('Discente', comp.descricao)
        self.assertEqual(comp.data_inicio, date(2026, 3, 1))

    def test_projeto_fora_do_escopo_bloqueado(self):
        """Sem elegibilidade o queryset já exclui o projeto (nem chega ao clean)."""
        self.client.login(username='alu_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_participacao'), {'projeto': self.projeto_alheio.pk},
        )
        self.assertContains(resp, 'escolha válida', status_code=200)
        self.assertFalse(
            Comprovante.objects.filter(
                tipo='participacao_projeto', pessoa=self.aluno1,
            ).exists(),
        )

    def test_tecnico_emite_para_membro(self):
        self.client.login(username='tec_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_participacao'),
            {'projeto': self.projeto_meu.pk, 'pessoa': self.aluno1.pk},
        )
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(tipo='participacao_projeto', pessoa=self.aluno1)
        self.assertEqual(comp.emitido_por, self.u_tec)

    def test_tecnico_escolhe_pessoa_fora_da_equipe(self):
        self.client.login(username='tec_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_participacao'),
            {'projeto': self.projeto_meu.pk, 'pessoa': self.aluno2.pk},
        )
        self.assertContains(resp, 'não integra a equipe', status_code=200)
        self.assertFalse(
            Comprovante.objects.filter(tipo='participacao_projeto').exists(),
        )


class EmissaoAvaliacaoTests(ComprovanteBase):
    """Comprovante de avaliação (§3.11 — avaliador de relatórios/propostas)."""

    def test_requer_exatamente_uma_opcao(self):
        self.client.login(username='doc_comp', password='x')
        url = reverse('comprovante_emitir_avaliacao')
        resp = self.client.post(url, {})
        self.assertContains(resp, 'exatamente uma opção', status_code=200)
        resp = self.client.post(
            url,
            {'relatorio': self.relatorio.pk, 'avaliacao': self.avaliacao.pk},
        )
        self.assertContains(resp, 'exatamente uma opção', status_code=200)
        self.assertFalse(Comprovante.objects.filter(tipo='avaliacao').exists())

    def test_docente_emite_avaliacao_de_relatorio(self):
        self.client.login(username='doc_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_avaliacao'), {'relatorio': self.relatorio.pk},
        )
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(tipo='avaliacao', bolsa=self.bolsa)
        self.assertEqual(comp.pessoa, self.docente)
        self.assertEqual(comp.projeto, self.projeto_meu)
        self.assertIn('nota 7,50', comp.descricao)

    def test_relatorio_alheio_nao_listado_no_form(self):
        self.client.login(username='doc_comp2', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_avaliacao'), {'relatorio': self.relatorio.pk},
        )
        self.assertContains(resp, 'escolha válida', status_code=200)
        self.assertFalse(Comprovante.objects.filter(tipo='avaliacao').exists())

    def test_docente_emite_avaliacao_de_proposta(self):
        self.client.login(username='doc_comp', password='x')
        resp = self.client.post(
            reverse('comprovante_emitir_avaliacao'), {'avaliacao': self.avaliacao.pk},
        )
        self.assertEqual(resp.status_code, 302)
        comp = Comprovante.objects.get(tipo='avaliacao', pessoa=self.docente)
        self.assertIn('Proposta comprovável', comp.descricao)
        self.assertIn('nota 8,00', comp.descricao)


class VerificacaoTests(ComprovanteBase):
    """Verificação pública pelo código (sem login)."""

    def test_verificar_publico(self):
        comp = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno1, projeto=self.projeto_meu,
            bolsa=self.bolsa, descricao='Minha bolsa',
        )
        url = reverse('comprovante_verificar', args=[comp.codigo_verificacao])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        conteudo = resp.content.decode()
        self.assertIn(self.aluno1.nome, conteudo)
        self.assertIn('Válido', conteudo)

    def test_codigo_inexistente_retorna_404(self):
        url = reverse('comprovante_verificar', args=['0' * 16])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


class PainelComprovantesTests(ComprovanteBase):
    """Seção de comprovantes no painel do aluno."""

    def test_painel_mostra_comprovantes(self):
        comp = Comprovante.objects.create(
            tipo='bolsa', pessoa=self.aluno1, projeto=self.projeto_meu,
            bolsa=self.bolsa, descricao='Minha bolsa',
        )
        self.client.login(username='alu_comp', password='x')
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, 'Seus comprovantes')
        self.assertContains(resp, reverse('comprovante_detalhe', args=[comp.pk]))

    def test_painel_sem_comprovantes_convida_a_emitir(self):
        self.client.login(username='alu_comp', password='x')
        resp = self.client.get(reverse('dashboard'))
        self.assertContains(resp, 'Emitir comprovante')
