"""Testes do módulo de Projetos (views, permissões e regra de negócio)."""
import re
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Perfil, Instituicao
from apps.projetos.forms import MAX_PROJETOS_SEM_FOMENTO
from apps.projetos.models import (
    AreaConhecimento,
    GrandeAreaConhecimento,
    ODS,
    Pessoa,
    Projeto,
    SubareaConhecimento,
)


def _criar_usuario(username, perfil, pessoa=None):
    user = User.objects.create_user(username, password='x')
    Perfil.objects.create(user=user, perfil=perfil, pessoa=pessoa)
    return user


def _dados_cnpq(**extras):
    """Ficha ODS + CNPq obrigatória, em cadeia coerente (GA→Área→Subárea)."""
    grande_area = GrandeAreaConhecimento.objects.first()
    area = grande_area.areas.first()
    subarea = area.subareas.first()
    return {
        'ods': [ODS.objects.first().pk],
        'grande_area': grande_area.pk,
        'area': area.pk,
        'subarea': subarea.pk,
        **extras,
    }


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

    def test_aluno_com_bolsa_ve_projeto_mesmo_sem_ser_membro(self):
        """Aluno com bolsa no projeto (sem ser membro) vê lista e detalhe."""
        from apps.bolsas.models import Bolsa, ModalidadeBolsa
        modalidade, _ = ModalidadeBolsa.objects.get_or_create(
            sigla='PIBIC', defaults={'nome': 'Iniciação Científica'},
        )
        Bolsa.objects.create(
            projeto=self.projeto, aluno=self.aluno_pessoa, modalidade=modalidade,
            data_inicio=date(2026, 3, 1), data_fim=date(2026, 11, 30),
        )
        self.client.login(username='alu', password='x')
        # Lista mostra o projeto
        response = self.client.get(reverse('projetos_lista'))
        self.assertContains(response, 'PVDI1-2026')
        # Detalhe acessível
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
            **_dados_cnpq(),
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


class PainelDocenteTests(TestCase):
    """O painel do docente deve listar seus projetos (vínculo por Pessoa, não e-mail)."""

    def setUp(self):
        self.docente = Pessoa.objects.create(
            nome='Docente Painel', email='painel@unifei.edu.br', tipo='docente',
        )
        self.projeto = _criar_projeto(self.docente)
        # E-mail do usuário DIFERENTE do e-mail da Pessoa (como no demo)
        self.user = User.objects.create_user('doc_painel', password='x')
        Perfil.objects.create(user=self.user, perfil=Perfil.PERFIL_DOCENTE, pessoa=self.docente)

    def test_painel_mostra_meus_projetos(self):
        self.client.login(username='doc_painel', password='x')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Meus projetos')
        self.assertContains(response, self.projeto.codigo)
        self.assertNotContains(response, 'Você ainda não possui projetos')
        # O código deve ser link para a página do projeto
        self.assertContains(
            response,
            reverse('projeto_detalhe', kwargs={'pk': self.projeto.pk}),
        )


class EdicaoValoresTests(TestCase):
    """O formulário de edição deve abrir com os valores do projeto."""

    def setUp(self):
        inst, _ = Instituicao.objects.get_or_create(sigla='EEI', defaults={'nome': 'EEI'})
        self.docente = Pessoa.objects.create(
            nome='Docente Edição', email='edicao@unifei.edu.br',
            tipo='docente', instituicao=inst,
        )
        self.user = _criar_usuario('doc_edicao', Perfil.PERFIL_DOCENTE, self.docente)
        self.projeto = Projeto.objects.create(
            codigo='PVDI777-2026',
            titulo='Projeto com datas',
            data_registro=date(2026, 1, 10),
            data_inicio=date(2026, 1, 15),
            data_termino=date(2026, 12, 20),
            coordenador=self.docente,
            instituicao=inst,
        )

    def test_form_abre_com_valores(self):
        """Datas em AAAA-MM-DD: o que o input date do HTML exige para exibir."""
        self.client.login(username='doc_edicao', password='x')
        response = self.client.get(
            reverse('projeto_editar', kwargs={'pk': self.projeto.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="PVDI777-2026"')
        self.assertContains(response, 'value="2026-01-15"')
        self.assertContains(response, 'value="2026-12-20"')

    def test_docente_nao_transfere_coordenacao(self):
        """POST alterando o coordenador é ignorado (campo desabilitado p/ docente)."""
        outro = Pessoa.objects.create(
            nome='Outro Coordenador', email='outro@unifei.edu.br', tipo='docente',
        )
        self.client.login(username='doc_edicao', password='x')
        response = self.client.post(
            reverse('projeto_editar', kwargs={'pk': self.projeto.pk}),
            {
                **_dados_cnpq(),
                'codigo': 'PVDI777-2026',
                'titulo': 'Projeto atualizado',
                'data_registro': '2026-01-10',
                'data_inicio': '2026-01-15',
                'data_termino': '2026-12-20',
                'status': 'vigente',
                'coordenador': outro.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.projeto.refresh_from_db()
        self.assertEqual(self.projeto.titulo, 'Projeto atualizado')
        self.assertEqual(self.projeto.coordenador, self.docente)


class GeracaoCodigoTests(TestCase):
    """Geração automática de código único no padrão PVDI###-AAAA (§3.1)."""

    def setUp(self):
        self.docente = Pessoa.objects.create(
            nome='Docente Código', email='cod@unifei.edu.br', tipo='docente',
        )
        self.user = _criar_usuario('tec_cod', Perfil.PERFIL_TECNICO)
        self.dados = {
            **_dados_cnpq(),
            'titulo': 'Projeto com código gerado',
            'data_registro': date.today().isoformat(),
            'data_inicio': date.today().isoformat(),
            'status': 'vigente',
            'coordenador': self.docente.pk,
        }

    def _post(self, **extras):
        """POST autenticado como técnico em /projetos/novo/."""
        self.client.login(username='tec_cod', password='x')
        return self.client.post(
            reverse('projeto_novo'), {**self.dados, **extras},
        )

    def test_form_exibe_sugestao_de_codigo(self):
        """GET do formulário: campo opcional já com sugestão gerada."""
        self.client.login(username='tec_cod', password='x')
        response = self.client.get(reverse('projeto_novo'))
        campo = response.context['form'].fields['codigo']
        self.assertFalse(campo.required)
        self.assertRegex(campo.initial, r'^PVDI\d{3,}-\d{4}$')

    def test_cria_sem_codigo_gera_sequencial(self):
        """POST sem código → sistema gera PVDI###-AAAA com o ano do registro."""
        response = self._post()
        self.assertEqual(response.status_code, 302)
        projeto = Projeto.objects.get(titulo='Projeto com código gerado')
        self.assertRegex(projeto.codigo, r'^PVDI\d{3,}-\d{4}$')
        self.assertTrue(projeto.codigo.endswith(f'-{date.today().year}'))

    def test_codigos_consecutivos_unicos_e_sequenciais(self):
        """Dois projetos seguidos recebem sequenciais distintos (n+1)."""
        self._post(titulo='Primeiro projeto')
        self._post(titulo='Segundo projeto')
        codigos = Projeto.objects.filter(
            titulo__in=['Primeiro projeto', 'Segundo projeto'],
        ).values_list('codigo', flat=True)
        numeros = sorted(
            int(re.match(r'^PVDI(\d+)', c).group(1)) for c in codigos
        )
        self.assertEqual(len(numeros), 2)
        self.assertEqual(numeros[1], numeros[0] + 1)

    def test_pula_sequencial_ja_existente(self):
        """Maior número existente no padrão define o próximo (sem colisão)."""
        Projeto.objects.create(
            codigo='PVDI050-2026',
            titulo='Projeto histórico',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente,
        )
        self._post()
        projeto = Projeto.objects.get(titulo='Projeto com código gerado')
        self.assertEqual(projeto.codigo, 'PVDI051-2026')

    def test_ano_do_codigo_segue_data_registro(self):
        """Ano do código = ano da data de registro, não o ano corrente."""
        self._post(data_registro='2024-06-01')
        projeto = Projeto.objects.get(titulo='Projeto com código gerado')
        self.assertEqual(projeto.codigo, 'PVDI001-2024')

    def test_codigo_explicito_e_preservado(self):
        """Código digitado (registro externo) é mantido, não substituído."""
        self._post(codigo='PVDI999-2019')
        self.assertTrue(
            Projeto.objects.filter(codigo='PVDI999-2019').exists(),
        )

    def test_edicao_com_codigo_em_branco_e_rejeitada(self):
        """Na edição o campo continua obrigatório e nunca é regenerado."""
        self._post(codigo='PVDI500-2026', titulo='Para editar')
        projeto = Projeto.objects.get(codigo='PVDI500-2026')
        response = self.client.post(
            reverse('projeto_editar', kwargs={'pk': projeto.pk}),
            {**self.dados, 'codigo': '', 'titulo': 'Editado'},
        )
        self.assertEqual(response.status_code, 200)  # volta com erro
        projeto.refresh_from_db()
        self.assertEqual(projeto.codigo, 'PVDI500-2026')
        self.assertEqual(projeto.titulo, 'Para editar')

    def test_codigo_duplicado_rejeitado(self):
        """Unicidade mantida: código igual a projeto existente é erro."""
        Projeto.objects.create(
            codigo='PVDI060-2026', titulo='Existe',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente,
        )
        response = self._post(codigo='PVDI060-2026')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'já existe')
        self.assertEqual(
            Projeto.objects.filter(codigo='PVDI060-2026').count(), 1,
        )


class OdsAreaConhecimentoTests(TestCase):
    """Ficha ODS + Área do Conhecimento do CNPq no projeto (obrigatórias)."""

    def setUp(self):
        self.docente = Pessoa.objects.create(
            nome='Docente Ficha', email='ficha@unifei.edu.br', tipo='docente',
        )
        self.user = _criar_usuario('tec_ficha', Perfil.PERFIL_TECNICO)
        self.base = {
            'titulo': 'Projeto com ficha ODS e CNPq',
            'data_registro': date.today().isoformat(),
            'data_inicio': date.today().isoformat(),
            'status': 'vigente',
            'coordenador': self.docente.pk,
        }

    def _post(self, **campos):
        """POST em /projetos/novo/ com ficha completa, sobrescrevível."""
        self.client.login(username='tec_ficha', password='x')
        return self.client.post(
            reverse('projeto_novo'),
            {**self.base, **_dados_cnpq(), **campos},
        )

    def _existe(self):
        return Projeto.objects.filter(
            titulo='Projeto com ficha ODS e CNPq',
        ).exists()

    # ------------------------------------------------------------------
    # Catálogo (migração de dados a partir do PDF do CNPq)
    # ------------------------------------------------------------------

    def test_catalogo_carregado_pela_migracao(self):
        self.assertEqual(ODS.objects.count(), 17)
        self.assertEqual(GrandeAreaConhecimento.objects.count(), 9)
        self.assertEqual(AreaConhecimento.objects.count(), 87)
        self.assertEqual(SubareaConhecimento.objects.count(), 366)

    def test_cadeia_do_catalogo_integra(self):
        """Toda área tem grande área e toda subárea tem área (sem órfãs)."""
        self.assertFalse(
            AreaConhecimento.objects.filter(grande_area__isnull=True).exists(),
        )
        self.assertFalse(
            SubareaConhecimento.objects.filter(area__isnull=True).exists(),
        )
        exatas = GrandeAreaConhecimento.objects.get(
            nome='Ciências Exatas e da Terra',
        )
        self.assertEqual(exatas.areas.count(), 8)
        matematica = AreaConhecimento.objects.get(nome='Matemática')
        self.assertEqual(matematica.grande_area, exatas)

    # ------------------------------------------------------------------
    # Criação
    # ------------------------------------------------------------------

    def test_criacao_com_ods_e_cascata_completa(self):
        ods_alvo = ODS.objects.get(numero=14)
        response = self._post(ods=[ods_alvo.pk])
        self.assertEqual(response.status_code, 302)
        projeto = Projeto.objects.get(titulo='Projeto com ficha ODS e CNPq')
        self.assertEqual(list(projeto.ods.all()), [ods_alvo])
        self.assertIsNotNone(projeto.grande_area_id)
        self.assertIsNotNone(projeto.area_id)
        self.assertIsNotNone(projeto.subarea_id)
        # cadeia coerente
        self.assertEqual(projeto.area.grande_area, projeto.grande_area)
        self.assertEqual(projeto.subarea.area, projeto.area)

    def test_criacao_sem_ods_e_rejeitada(self):
        response = self._post(ods=[])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'obrigatório')
        self.assertFalse(self._existe())

    def test_criacao_sem_cnpq_e_rejeitada(self):
        response = self._post(grande_area='', area='', subarea='')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'obrigatório')
        self.assertFalse(self._existe())

    def test_area_de_grande_area_diferente_rejeitada(self):
        cnpq = _dados_cnpq()
        outra_ga = GrandeAreaConhecimento.objects.exclude(
            pk=cnpq['grande_area'],
        ).first()
        response = self._post(grande_area=outra_ga.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não pertence')
        self.assertFalse(self._existe())

    def test_subarea_de_area_diferente_rejeitada(self):
        cnpq = _dados_cnpq()
        outra_sub = SubareaConhecimento.objects.exclude(
            area_id=cnpq['area'],
        ).first()
        response = self._post(subarea=outra_sub.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não pertence')
        self.assertFalse(self._existe())

    # ------------------------------------------------------------------
    # Edição e exibição
    # ------------------------------------------------------------------

    def test_edicao_exige_ficha_completa(self):
        """Registro antigo (sem ficha) só salva depois de completar ODS+CNPq."""
        projeto = Projeto.objects.create(
            codigo='PVDI400-2026', titulo='Projeto antigo sem ficha',
            data_registro=date.today(), data_inicio=date.today(),
            coordenador=self.docente,
        )
        self.client.login(username='tec_ficha', password='x')
        url = reverse('projeto_editar', kwargs={'pk': projeto.pk})
        # O registro antigo continua abrindo para complementação
        self.assertEqual(self.client.get(url).status_code, 200)
        # Sem a ficha, a edição é bloqueada
        response = self.client.post(url, {
            'codigo': 'PVDI400-2026',
            'titulo': 'Projeto antigo sem ficha',
            'data_registro': date.today().isoformat(),
            'data_inicio': date.today().isoformat(),
            'status': 'vigente',
            'coordenador': self.docente.pk,
        })
        self.assertEqual(response.status_code, 200)
        projeto.refresh_from_db()
        self.assertIsNone(projeto.grande_area_id)
        # Com a ficha completa, salva
        response = self.client.post(url, {
            **_dados_cnpq(),
            'codigo': 'PVDI400-2026',
            'titulo': 'Projeto antigo sem ficha',
            'data_registro': date.today().isoformat(),
            'data_inicio': date.today().isoformat(),
            'status': 'vigente',
            'coordenador': self.docente.pk,
        })
        self.assertEqual(response.status_code, 302)
        projeto.refresh_from_db()
        self.assertIsNotNone(projeto.subarea_id)
        self.assertEqual(projeto.ods.count(), 1)

    def test_detalhe_exibe_ods_e_areas(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        projeto = Projeto.objects.get(titulo='Projeto com ficha ODS e CNPq')
        detalhe = self.client.get(
            reverse('projeto_detalhe', kwargs={'pk': projeto.pk}),
        )
        self.assertContains(detalhe, 'ODS 1 - Erradicação da pobreza')
        self.assertContains(detalhe, 'Ciências Exatas e da Terra')
        self.assertContains(detalhe, 'Matemática')
        self.assertContains(detalhe, 'Álgebra')

    def test_form_exibe_checkboxes_ods_e_mapa_da_cascata(self):
        self.client.login(username='tec_ficha', password='x')
        response = self.client.get(reverse('projeto_novo'))
        # checkboxes dos 17 ODS
        self.assertContains(response, 'id_ods_0')
        self.assertContains(response, 'Erradicação da pobreza')
        # mapa da hierarquia + script da cascata
        self.assertContains(response, 'hierarquia-cnpq')
        self.assertContains(response, 'cascata_cnpq.js')
