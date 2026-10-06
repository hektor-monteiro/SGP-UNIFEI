import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import Instituicao, Fomentador
from apps.projetos.models import Pessoa, Projeto, Proposta
from apps.bolsas.models import ModalidadeBolsa, Bolsa, Indicacao
from apps.editais.models import Edital, Avaliacao, CriterioAvaliacao
from apps.equipes.models import MembroEquipe
from apps.comprovantes.models import Comprovante
from apps.relatorios.models import PlanoTrabalho, Relatorio

class Command(BaseCommand):
    help = 'Popula o banco de dados com dados simulados baseados na planilha real'

    def handle(self, *args, **options):
        self.stdout.write('Iniciando população de dados simulados...')

        instituicoes = self.criar_instituicoes()
        self.stdout.write(f'  ✓ {len(instituicoes)} instituições criadas')

        fomentadores = self.criar_fomentadores()
        self.stdout.write(f'  ✓ {len(fomentadores)} fomentadores criadas')

        modalidades = self.criar_modalidades()
        self.stdout.write(f'  ✓ {len(modalidades)} modalidades criadas')

        alunos, docentes, externos = self.criar_pessoas(instituicoes)
        self.stdout.write(f'  ✓ {len(alunos)} alunos, {len(docentes)} docentes e {len(externos)} externos criados')

        projetos = self.criar_projetos(docentes, instituicoes, fomentadores)
        self.stdout.write(f'  ✓ {len(projetos)} projetos criados')

        self.criar_equipes(projetos, alunos, docentes, externos)
        self.stdout.write('  ✓ Equipes criadas')

        bolsas = self.criar_bolsas(projetos, alunos, modalidades, fomentadores)
        self.stdout.write(f'  ✓ {len(bolsas)} bolsas criadas')

        self.criar_planos_trabalho(bolsas, alunos)
        self.stdout.write('  ✓ Planos de trabalho criados')

        self.criar_relatorios(bolsas, alunos)
        self.stdout.write('  ✓ Relatórios criados')

        editais = self.criar_editais(modalidades)
        self.stdout.write(f'  ✓ {len(editais)} editais criados')

        self.criar_propostas(editais, docentes, projetos)
        self.stdout.write('  ✓ Propostas criadas')

        indicacoes = self.criar_indicacoes(alunos)
        self.stdout.write(f'  ✓ {indicacoes} indicações de cotas criadas')

        self.criar_comprovantes(bolsas, projetos, alunos, docentes)
        self.stdout.write('  ✓ Comprovantes criados')

        usuarios = self.criar_usuarios_demo(alunos, docentes)
        self.stdout.write(f'  ✓ {len(usuarios)} usuários demo criados')

        criterios = self.criar_criterios()
        self.stdout.write(f'  ✓ {len(criterios)} critérios de avaliação criados')

        alocacoes = self.criar_avaliacoes(editais)
        self.stdout.write(f'  ✓ {alocacoes} alocações de avaliação criadas')

        self.stdout.write(self.style.SUCCESS('População concluída com sucesso!'))

    def criar_usuarios_demo(self, alunos, docentes):
        """Cria um usuário demo por perfil de acesso (senha: demo123)."""
        from django.contrib.auth.models import User
        from apps.core.models import Perfil

        usuarios = []

        def get_or_create_user(username, email):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email},
            )
            if created:
                user.set_password('demo123')
                user.save()
            return user

        # Aluno
        u = get_or_create_user('aluno1', 'aluno1@alunos.edu.br')
        Perfil.objects.get_or_create(user=u, defaults={'perfil': Perfil.PERFIL_ALUNO, 'pessoa': alunos[0] if alunos else None})
        usuarios.append('aluno1')

        # Docente (vinculado ao primeiro docente, que é coordenador de projetos)
        u = get_or_create_user('docente1', 'docente1@unifei.edu.br')
        Perfil.objects.get_or_create(user=u, defaults={'perfil': Perfil.PERFIL_DOCENTE, 'pessoa': docentes[0] if docentes else None})
        usuarios.append('docente1')

        # Técnico administrativo
        u = get_or_create_user('tecnico1', 'tecnico1@unifei.edu.br')
        Perfil.objects.get_or_create(user=u, defaults={'perfil': Perfil.PERFIL_TECNICO})
        usuarios.append('tecnico1')

        # Diretor de Pesquisa
        u = get_or_create_user('diretor1', 'diretor1@unifei.edu.br')
        Perfil.objects.get_or_create(user=u, defaults={'perfil': Perfil.PERFIL_DIRETOR})
        usuarios.append('diretor1')

        # Pro-reitor
        u = get_or_create_user('proreitor1', 'proreitor1@unifei.edu.br')
        Perfil.objects.get_or_create(user=u, defaults={'perfil': Perfil.PERFIL_PROREITOR})
        usuarios.append('proreitor1')

        return usuarios

    def criar_instituicoes(self):
        instituicoes_data = [
            ('IMC', 'Instituto de Matemática e Computação'),
            ('ISEE', 'Instituto de Sistemas Elétricos e Energia'),
            ('IFQ', 'Instituto de Física e Química'),
            ('IRN', 'Instituto de Recursos Naturais'),
            ('EXCEN', 'Excelência em Ciências Exatas e Naturais'),
        ]
        instituicoes = []
        for sigla, nome in instituicoes_data:
            inst, _ = Instituicao.objects.get_or_create(sigla=sigla, defaults={'nome': nome})
            instituicoes.append(inst)
        return instituicoes

    def criar_fomentadores(self):
        fomentadores_data = [
            ('FAPEMIG', 'Fundação de Amparo à Pesquisa do Estado de Minas Gerais', 'projeto'),
            ('CNPq', 'Conselho Nacional de Desenvolvimento Científico e Tecnológico', 'bolsa'),
            ('UNIFEI', 'Universidade Federal de Itajubá', 'bolsa'),
            ('CAPES', 'Coordenação de Aperfeiçoamento de Pessoal de Nível Superior', 'bolsa'),
        ]
        fomentadores = []
        for sigla, nome, tipo in fomentadores_data:
            fom, _ = Fomentador.objects.get_or_create(sigla=sigla, defaults={'nome': nome, 'tipo': tipo})
            fomentadores.append(fom)
        return fomentadores

    def criar_modalidades(self):
        modalidades_data = [
            ('PIBIC', 'Programa Institucional de Bolsas de Iniciação Científica'),
            ('PIBITI', 'Programa Institucional de Bolsas de Iniciação em Desenvolvimento Tecnológico e Inovação'),
            ('PIVIC', 'Programa Institucional de Voluntários de Iniciação Científica'),
        ]
        modalidades = []
        for sigla, nome in modalidades_data:
            mod, _ = ModalidadeBolsa.objects.get_or_create(sigla=sigla, defaults={'nome': nome})
            modalidades.append(mod)
        return modalidades

    def criar_pessoas(self, instituicoes):
        nomes_alunos = [
            'Ana Beatriz Silva', 'Bruno Oliveira', 'Camila Santos', 'Daniel Costa',
            'Eduarda Lima', 'Felipe Pereira', 'Gabriela Rodrigues', 'Henrique Almeida',
            'Isabela Fernandes', 'João Pedro Martins', 'Larissa Souza', 'Matheus Ribeiro',
            'Natália Gomes', 'Otávio Cardoso', 'Patrícia Moreira', 'Rafael Barbosa',
            'Sofia Nascimento', 'Thiago Araújo', 'Vitória Dias', 'William Ferreira',
        ]
        nomes_docentes = [
            'Adhimar Flávio Oliveira', 'Alexander Fernandes da Fonseca',
            'André Carlos Bragança Ramos', 'Denis de Carvalho Braga',
            'Edisom de Souza Moreira Júnior', 'Fábio Scalco Dias',
            'Juliana Garcia Cespedes', 'Luis Fernando de Osório Mello',
            'Marcos Vinícius Xavier Dias', 'Mariana Feiteiro Cavalari Silva',
        ]
        alunos = []
        docentes = []
        for i, nome in enumerate(nomes_alunos):
            email = f'{nome.lower().replace(" ", ".")}@alunos.edu.br'
            aluno, _ = Pessoa.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'tipo': 'aluno',
                    'matricula': f'2024{i:04d}',
                    'instituicao': random.choice(instituicoes),
                }
            )
            alunos.append(aluno)
        for i, nome in enumerate(nomes_docentes):
            email = f'{nome.lower().replace(" ", ".")}@unifei.edu.br'
            docente, _ = Pessoa.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'tipo': 'docente',
                    'instituicao': random.choice(instituicoes),
                }
            )
            docentes.append(docente)
        nomes_externos = [
            'Carlos Roberto Mendes', 'Patrícia Alves de Souza',
        ]
        externos = []
        for nome in nomes_externos:
            email = f'{nome.lower().replace(" ", ".")}@parceiro.com.br'
            externo, _ = Pessoa.objects.get_or_create(
                email=email,
                defaults={
                    'nome': nome,
                    'tipo': 'externo',
                    'instituicao': random.choice(instituicoes),
                }
            )
            externos.append(externo)
        return alunos, docentes, externos

    def criar_projetos(self, docentes, instituicoes, fomentadores):
        titulos = [
            'Síntese Verde de Nanopartículas de Dióxido de Titânio para Fotocatálise',
            'Desenvolvimento de Sistema de Software para Treinamento em Simulador',
            'Narrativas sobre Mídias Digitais e Redes Sociais na Educação Científica',
            'Ciclos Limites em Sistemas Hamiltonianos Quadráticos',
            'Radiação de Corpo Negro Escalar na Presença de Fronteiras',
            'Geometria de Curvas Planas e Sistemas Hamiltonianos',
            'Inteligência Artificial Aplicada à Otimização de Processos Industriais',
            'Estudo de Materiais Sustentáveis para Construção Civil',
            'Análise de Dados para Previsão de Demanda Energética',
            'Desenvolvimento de Biossensores para Monitoramento Ambiental',
        ]
        projetos = []
        for i, titulo in enumerate(titulos):
            codigo = f'PVDI{random.randint(100, 999)}-2024'
            # Sempre há projetos concluídos (variedade p/ indicadores §5.1)
            status = 'concluido' if i in (3, 8) else random.choice(
                ['vigente', 'vigente', 'expirado'],
            )
            if status == 'concluido':
                # Projeto concluído termina no passado; início anterior ao término
                data_termino = datetime.now() - timedelta(days=random.randint(15, 180))
                data_inicio = data_termino - timedelta(days=random.randint(120, 720))
            else:
                data_inicio = datetime.now() - timedelta(days=random.randint(10, 180))
                data_termino = datetime.now() + timedelta(days=random.randint(30, 365))
            projeto, created = Projeto.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'titulo': titulo,
                    'data_registro': data_inicio - timedelta(days=random.randint(5, 60)),
                    'data_inicio': data_inicio,
                    'data_termino': data_termino,
                    'status': status,
                    'coordenador': docentes[i % len(docentes)],
                    'instituicao': random.choice(instituicoes),
                    'fomentador': random.choice(fomentadores) if random.random() > 0.3 else None,
                    # Recursos vinculados alimentam a execução orçamentária (§5.1)
                    'recursos_internos': round(random.uniform(5000, 80000), 2),
                    'recursos_externos': (
                        round(random.uniform(10000, 150000), 2) if random.random() > 0.4 else None
                    ),
                }
            )
            projetos.append(projeto)
        return projetos

    def criar_equipes(self, projetos, alunos, docentes, externos):
        for i, projeto in enumerate(projetos):
            MembroEquipe.objects.get_or_create(
                projeto=projeto,
                pessoa=projeto.coordenador,
                funcao='coordenador',
                defaults={
                    'carga_horaria': random.choice([8, 10, 12, 20]),
                    'data_entrada': projeto.data_inicio,
                }
            )
            for _ in range(random.randint(1, 3)):
                aluno = random.choice(alunos)
                MembroEquipe.objects.get_or_create(
                    projeto=projeto,
                    pessoa=aluno,
                    funcao='discente',
                    defaults={
                        'carga_horaria': random.choice([10, 12, 20]),
                        'data_entrada': projeto.data_inicio,
                    }
                )
            for _ in range(random.randint(0, 2)):
                docente = random.choice(docentes)
                if docente != projeto.coordenador:
                    MembroEquipe.objects.get_or_create(
                        projeto=projeto,
                        pessoa=docente,
                        funcao='docente',
                        defaults={
                            'carga_horaria': random.choice([4, 8, 10]),
                            'data_entrada': projeto.data_inicio,
                        }
                    )
            # Colaboradores externos sempre em parte dos projetos (§5.1)
            if externos and (i % 3 == 0 or random.random() > 0.7):
                MembroEquipe.objects.get_or_create(
                    projeto=projeto,
                    pessoa=random.choice(externos),
                    funcao='externo',
                    defaults={
                        'carga_horaria': random.choice([4, 8]),
                        'data_entrada': projeto.data_inicio,
                    },
                )

    def criar_bolsas(self, projetos, alunos, modalidades, fomentadores):
        bolsas = []
        alunos_usados = set()
        for projeto in projetos:
            for _ in range(random.randint(1, 2)):
                disponiveis = [a for a in alunos if a.id not in alunos_usados]
                if not disponiveis:
                    break
                # Primeira bolsa sempre do aluno demo (aluno1 = alunos[0]),
                # para o painel inicial não nascer vazio em instalação nova
                aluno = (
                    alunos[0] if not alunos_usados and alunos
                    else random.choice(disponiveis)
                )
                alunos_usados.add(aluno.id)
                # Idempotência: alunos que já têm bolsa de execução anterior
                # são pulados (o get_or_create por aluno não é único e
                # `MultipleObjectsReturned` quebrava a reexecução da seed)
                if Bolsa.objects.filter(aluno=aluno).exists():
                    continue
                bolsa, created = Bolsa.objects.get_or_create(
                    aluno=aluno,
                    defaults={
                        'projeto': projeto,
                        'modalidade': random.choice(modalidades),
                        'fomentador': random.choice(fomentadores),
                        'data_inicio': projeto.data_inicio,
                        'data_fim': projeto.data_termino or (datetime.now() + timedelta(days=365)),
                        # Bolsa de projeto concluído já se encerrou (§5.1 e §5.2)
                        'status': 'encerrada' if projeto.status == 'concluido' else 'ativa',
                        'valor_mensal': random.choice([400.00, 500.00, 600.00, 700.00]),
                    }
                )
                if created:
                    bolsas.append(bolsa)
        # Segunda bolsa já encerrada para alguns alunos: alimenta o indicador
        # de retenção/renovação de bolsistas (§5.2)
        for aluno_id in list(alunos_usados)[:5]:
            aluno = next(a for a in alunos if a.id == aluno_id)
            projeto = random.choice(projetos)
            bolsa, created = Bolsa.objects.get_or_create(
                aluno=aluno,
                projeto=projeto,
                defaults={
                    'modalidade': random.choice(modalidades),
                    'fomentador': random.choice(fomentadores),
                    'data_inicio': projeto.data_inicio - timedelta(days=365),
                    'data_fim': projeto.data_inicio,
                    'status': 'encerrada',
                    'valor_mensal': random.choice([400.00, 500.00, 600.00, 700.00]),
                },
            )
            if created:
                bolsas.append(bolsa)
        return bolsas

    def criar_planos_trabalho(self, bolsas, alunos):
        for bolsa in bolsas:
            PlanoTrabalho.objects.get_or_create(
                bolsa=bolsa,
                defaults={
                    'aluno': bolsa.aluno,
                    'projeto': bolsa.projeto,
                    'titulo': f'Plano de Trabalho - {bolsa.modalidade.sigla}',
                    'descricao': 'Plano de trabalho para iniciação científica',
                    'objetivos': 'Desenvolver pesquisa científica na área de estudo',
                    'metodologia': 'Revisão bibliográfica, experimentação e análise de dados',
                    'status': random.choice(['rascunho', 'submetido', 'aprovado']),
                }
            )

    def criar_relatorios(self, bolsas, alunos):
        """Cria um parcial e um final por bolsa, coerentes com o fluxo:
        nota/avaliação apenas nos status avaliados; nota na faixa certa
        (aprovado >= 6,00; reprovado < 6,00)."""
        for bolsa in bolsas:
            for tipo in ['parcial', 'final']:
                status = random.choice(['rascunho', 'submetido', 'aprovado', 'reprovado'])
                avaliado = status in ('aprovado', 'reprovado')
                if status == 'aprovado':
                    nota = round(random.uniform(6.0, 10.0), 2)
                elif status == 'reprovado':
                    nota = round(random.uniform(3.0, 5.95), 2)
                else:
                    nota = None
                agora = timezone.now()
                # Só cria se ainda não existir (parciais podem se repetir na base)
                if not Relatorio.objects.filter(bolsa=bolsa, tipo=tipo).exists():
                    Relatorio.objects.create(
                        bolsa=bolsa,
                        tipo=tipo,
                        aluno=bolsa.aluno,
                        titulo=f'Relatório {tipo.capitalize()} - {bolsa.modalidade.sigla}',
                        conteudo=f'Conteúdo do relatório {tipo}...',
                        status=status,
                        nota=nota,
                        observacoes='Avaliação de demonstração.' if avaliado else '',
                        avaliado_por=bolsa.projeto.coordenador if avaliado else None,
                        data_avaliacao=agora if avaliado else None,
                        data_submissao=agora if status != 'rascunho' else None,
                    )

    def criar_editais(self, modalidades):
        editais = []
        for i, modalidade in enumerate(modalidades):
            edital, _ = Edital.objects.get_or_create(
                codigo=f'{modalidade.sigla}-2024-01',
                defaults={
                    'titulo': f'Edital {modalidade.sigla} 2024',
                    'descricao': f'Edital para seleção de propostas {modalidade.sigla}',
                    'data_inicio': datetime.now() - timedelta(days=30),
                    'data_fim': datetime.now() + timedelta(days=60),
                    'status': random.choice(['aprovado', 'em_andamento', 'encerrado']),
                    'modalidade': modalidade,
                }
            )
            editais.append(edital)
        return editais

    def criar_propostas(self, editais, docentes, projetos):
        """Propostas de docentes solicitando cotas para seus projetos (§3.5)."""
        criadas = []
        for edital in editais:
            for _ in range(random.randint(2, 5)):
                proposta, _ = Proposta.objects.get_or_create(
                    titulo=f'Proposta para {edital.codigo} - {random.randint(1, 100)}',
                    defaults={
                        'resumo': 'Resumo da proposta de pesquisa...',
                        'edital': edital,
                        'projeto': random.choice(projetos) if projetos else None,
                        'cotas': random.randint(1, 3),
                        'submetido_por': random.choice(docentes),
                        'status': random.choice(['submetida', 'em_avaliacao', 'aprovada', 'reprovada']),
                        'nota_final': round(random.uniform(6.0, 10.0), 2) if random.random() > 0.5 else None,
                    }
                )
                criadas.append(proposta)
        return criadas

    def criar_indicacoes(self, alunos):
        """Indicações pendentes de alunos em propostas aprovadas (§3.5).

        Considera todas as propostas aprovadas com projeto (não apenas as
        sorteadas nesta execução) e usa apenas alunos sem bolsa ativa, para
        que a implementação pelo técnico funcione no demo.
        """
        com_bolsa = set(
            Bolsa.objects.filter(status='ativa').values_list('aluno_id', flat=True)
        )
        disponiveis = [a for a in alunos if a.pk not in com_bolsa]
        random.shuffle(disponiveis)
        criadas = 0
        aprovadas = list(
            Proposta.objects.filter(status='aprovada', projeto__isnull=False)
        )
        cursor = 0
        for proposta in aprovadas[:4]:
            quantidade = max(
                0, min(proposta.cotas, 2, len(disponiveis) - cursor),
            )
            if not quantidade:
                break
            for aluno in disponiveis[cursor:cursor + quantidade]:
                _, created = Indicacao.objects.get_or_create(
                    proposta=proposta,
                    aluno=aluno,
                    defaults={'indicado_por': proposta.submetido_por},
                )
                if created:
                    criadas += 1
            cursor += quantidade
        return criadas

    def criar_criterios(self):
        """Cria critérios de avaliação com pesos (usados na média ponderada)."""
        criterios = []
        dados = [
            ('Relevância do tema', 'Contribuição do tema para a área e para a UNIFEI.', 3.00),
            ('Metodologia', 'Adequação do método proposto aos objetivos.', 3.00),
            ('Viabilidade', 'Viabilidade técnica, prazos e recursos disponíveis.', 2.00),
        ]
        for nome, descricao, peso in dados:
            criterio, _ = CriterioAvaliacao.objects.get_or_create(
                nome=nome,
                defaults={'descricao': descricao, 'peso': peso},
            )
            criterios.append(criterio)
        return criterios

    def criar_avaliacoes(self, editais):
        """Aloca os usuários docentes como avaliadores de algumas propostas."""
        from django.contrib.auth.models import User

        docentes = list(
            User.objects.filter(perfil__perfil='docente').order_by('username')
        )
        if not docentes:
            return 0

        alocadas = 0
        propostas = Proposta.objects.filter(
            edital__in=editais, status='submetida',
        ).order_by('data_submissao')[:4]
        for proposta in propostas:
            avaliador = docentes[alocadas % len(docentes)]
            _, created = Avaliacao.objects.get_or_create(
                tipo='proposta',
                proposta=proposta,
                avaliador=avaliador,
                defaults={'status': 'alocada'},
            )
            if created:
                alocadas += 1
                proposta.status = 'em_avaliacao'
                proposta.save()
        return alocadas

    def criar_comprovantes(self, bolsas, projetos, alunos, docentes):
        for bolsa in bolsas:
            Comprovante.objects.get_or_create(
                tipo='bolsa',
                pessoa=bolsa.aluno,
                bolsa=bolsa,
                defaults={
                    'projeto': bolsa.projeto,
                    'descricao': f'Comprovante de bolsa {bolsa.modalidade.sigla}',
                    'data_inicio': bolsa.data_inicio,
                    'data_fim': bolsa.data_fim,
                }
            )
        for projeto in projetos:
            Comprovante.objects.get_or_create(
                tipo='participacao_projeto',
                pessoa=projeto.coordenador,
                projeto=projeto,
                defaults={
                    'descricao': f'Comprovante de coordenação do projeto {projeto.codigo}',
                    'data_inicio': projeto.data_inicio,
                    'data_fim': projeto.data_termino,
                }
            )
