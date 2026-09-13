from django.core.management.base import BaseCommand

from core.models import ContentBlock
from core import chatbot


class Command(BaseCommand):
    help = 'Calcula embeddings (Workers AI) para os ContentBlock que ainda não têm — ou todos, com --force.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Recalcula mesmo os blocos que já têm embedding.')

    def handle(self, *args, **options):
        blocks = ContentBlock.objects.all() if options['force'] else ContentBlock.objects.filter(embedding__isnull=True)

        total = blocks.count()
        if not total:
            self.stdout.write('Nada para indexar.')
            return

        ok, failed, skipped = 0, 0, 0
        for block in blocks:
            if not chatbot.block_index_text(block):
                skipped += 1
                continue
            chatbot.update_block_embedding(block)
            block.refresh_from_db(fields=['embedding'])
            if block.embedding:
                ok += 1
            else:
                failed += 1

        self.stdout.write(self.style.SUCCESS(f'{ok}/{total} bloco(s) indexado(s).'))
        if skipped:
            self.stdout.write(f'{skipped} bloco(s) sem texto (ignorados).')
        if failed:
            self.stdout.write(self.style.WARNING(f'{failed} bloco(s) falharam — confira CF_ACCOUNT_ID/CF_API_TOKEN.'))
