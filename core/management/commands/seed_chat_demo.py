from django.core.management.base import BaseCommand
from django.utils.text import slugify

from core.models import MinorTopic, ContentBlock
from core import chatbot

DEMO_CONTENT = [
    ('Como Criar SA', ContentBlock.CHECKLIST, 'Passo a passo', (
        'Acesse o sistema SIS com seu login\n'
        'Localize o cliente pelo CPF ou código do contrato\n'
        'Clique em "Nova SA" no menu de atendimento\n'
        'Selecione o tipo de solicitação (manutenção, mudança de plano, etc.)\n'
        'Preencha a justificativa com o relato do cliente\n'
        'Confirme o endereço de atendimento\n'
        'Clique em "Abrir SA" e anote o protocolo gerado'
    )),
    ('Erros ao Abrir SA', ContentBlock.TEXT, 'Erros mais comuns', (
        'Se aparecer "cliente bloqueado", verifique se há fatura em atraso antes de abrir a SA. '
        'Se aparecer "endereço divergente", confirme o endereço de atendimento com o cliente e atualize o cadastro '
        'antes de tentar novamente. Se o sistema travar na confirmação, atualize a página e reabra o atendimento '
        '— não feche o navegador, pois a SA pode já ter sido criada em duplicidade.'
    )),
    ('Como Abrir GLPI', ContentBlock.CHECKLIST, 'Passo a passo', (
        'Acesse o GLPI com seu login de atendente\n'
        'Clique em "Criar chamado"\n'
        'Selecione a categoria correspondente ao problema\n'
        'Descreva o problema com o máximo de detalhes técnicos\n'
        'Anexe prints ou logs se houver\n'
        'Defina a prioridade conforme o impacto no cliente\n'
        'Envie e acompanhe pelo número do chamado'
    )),
    ('Manutenção', ContentBlock.TEXT, 'Fluxo de manutenção', (
        'Ao identificar uma solicitação de manutenção, primeiro confirme se o problema é pontual (um cliente) ou '
        'se há uma massiva na região. Teste a conexão remotamente pelo sistema antes de agendar visita técnica. '
        'Se o problema persistir, abra uma SA de manutenção e, se for necessário suporte da rede, acione o NOC '
        'pelo GLPI.'
    )),
]


class Command(BaseCommand):
    help = 'Cria conteúdo fake nos tópicos já semeados, para testar o chatbot (RAG) localmente.'

    def handle(self, *args, **kwargs):
        created = 0
        for minor_title, block_type, block_title, text in DEMO_CONTENT:
            minor = MinorTopic.objects.filter(slug=slugify(minor_title)).first()
            if not minor:
                self.stdout.write(self.style.WARNING(
                    f'  Sub-tópico "{minor_title}" não encontrado — rode "manage.py seed" primeiro.'
                ))
                continue

            if minor.blocks.filter(title=block_title).exists():
                self.stdout.write(f'  Bloco "{block_title}" já existe em "{minor_title}".')
                continue

            block = ContentBlock.objects.create(
                minor_topic=minor,
                block_type=block_type,
                title=block_title,
                content=text,
                order=minor.blocks.count(),
            )
            chatbot.update_block_embedding(block)
            block.refresh_from_db()
            status = 'com embedding' if block.embedding else 'SEM embedding (falhou a chamada à Workers AI)'
            self.stdout.write(f'  Bloco "{block_title}" criado em "{minor_title}" ({status}).')
            created += 1

        if created:
            self.stdout.write(self.style.SUCCESS(f'{created} bloco(s) de teste criado(s).'))
        else:
            self.stdout.write('Nenhum bloco novo criado.')
