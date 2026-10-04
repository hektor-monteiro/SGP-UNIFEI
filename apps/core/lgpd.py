"""Utilitários de conformidade LGPD (§6): anonimização de dados pessoais.

A exclusão de dados pessoais no SGP-UNIFEI é implementada como
**anonimização irreversível**: os registros de pesquisa, bolsas,
relatórios e auditoria são preservados (prestação de contas), mas os
dados que identificam a pessoa são substituídos de forma que ela não
possa mais ser identificada a partir do sistema.
"""
from django.contrib.auth.models import User
from django.db import transaction


def vinculos_ativos(pessoa) -> list:
    """Lista os vínculos que impedem a anonimização de `pessoa`.

    Enquanto houver obrigação vigente (bolsa, projeto, plano ou relatório
    em andamento), os dados ainda são necessários às finalidades do
    sistema — nesses casos a solicitação de exclusão deve ser indeferida
    (art. 16 da LGPD: dados necessários ao cumprimento de obrigação legal).
    """
    # Imports locais: evitam ciclo de imports entre apps.
    from apps.bolsas.models import Bolsa
    from apps.equipes.models import MembroEquipe
    from apps.projetos.models import Projeto
    from apps.relatorios.models import PlanoTrabalho, Relatorio

    bloqueios = []
    if Bolsa.objects.filter(aluno=pessoa, status='ativa').exists():
        bloqueios.append('possui bolsa ativa')
    if MembroEquipe.objects.filter(
        pessoa=pessoa, ativo=True, projeto__status='vigente',
    ).exists():
        bloqueios.append('é membro ativo de projeto vigente')
    if Projeto.objects.filter(coordenador=pessoa, status='vigente').exists():
        bloqueios.append('coordena projeto vigente')
    if PlanoTrabalho.objects.filter(
        aluno=pessoa, status__in=('rascunho', 'submetido'),
    ).exists():
        bloqueios.append('possui plano de trabalho em andamento')
    if Relatorio.objects.filter(aluno=pessoa, status='submetido').exists():
        bloqueios.append('possui relatório aguardando avaliação')
    return bloqueios


def anonimizar_titular(user: User) -> None:
    """Anonimiza de forma irreversível os dados pessoais de `user`.

    - Pessoa: nome, e-mail, CPF, matrícula e Lattes são substituídos;
      o registro permanece para preservar as relações (bolsas, equipes,
      relatórios) como evidência de prestação de contas.
    - Usuário: username/e-mail/nomes são substituídos, a senha é
      invalidada (não é mais possível entrar) e o consentimento é
      revogado. O id é mantido — logs de auditoria e FKs continuam
      íntegros, porém sem identificar a pessoa.
    """
    with transaction.atomic():
        perfil = getattr(user, 'perfil', None)
        pessoa = perfil.pessoa if perfil and perfil.pessoa_id else None

        if pessoa is not None:
            sufixo = str(pessoa.pk).replace('-', '')[:8]
            pessoa.nome = f'Titular anonimizado ({sufixo})'
            pessoa.email = f'anonimo-{sufixo}@anonimizado.invalid'
            pessoa.cpf = ''
            pessoa.matricula = None
            pessoa.lattes = ''
            pessoa.ativo = False
            pessoa.save(update_fields=[
                'nome', 'email', 'cpf', 'matricula', 'lattes', 'ativo',
                'atualizado_em',
            ])

        sufixo_user = str(user.pk).replace('-', '')[:8]
        user.username = f'anonimo-{sufixo_user}'
        user.email = ''
        user.first_name = ''
        user.last_name = ''
        user.set_unusable_password()
        user.save(update_fields=[
            'username', 'email', 'first_name', 'last_name', 'password',
        ])

        if perfil is not None:
            perfil.consentimento_lgpd = False
            perfil.data_consentimento = None
            perfil.save(update_fields=[
                'consentimento_lgpd', 'data_consentimento', 'atualizado_em',
            ])
