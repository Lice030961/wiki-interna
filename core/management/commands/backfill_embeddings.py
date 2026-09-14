from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import ContentBlock
from core import chatbot


class Command(BaseCommand):
    help = 'Calcula embeddings (Workers AI) para os ContentBlock que ainda não têm — ou todos, com --force.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Recalcula mesmo os blocos que já têm embedding.')
        parser.add_argument(
            '--recaption-images', action='store_true',
            help='Limpa a image_description de todo bloco de imagem e gera de novo com o CF_VISION_MODEL '
                 'atual (usar depois de trocar o modelo de visão, pra reprocessar imagens já cadastradas).',
        )

    def handle(self, *args, **options):
        if options['recaption_images']:
            ContentBlock.objects.filter(block_type=ContentBlock.IMAGE).exclude(image_description='').update(
                image_description=''
            )

        if options['force']:
            blocks = ContentBlock.objects.all()
        else:
            # --recaption-images já limpou image_description acima, então esse filtro sozinho
            # pega todo bloco de imagem pra reprocessar, sem tocar nos blocos de texto que já
            # têm embedding (mais barato que rodar tudo de novo com --force).
            blocks = ContentBlock.objects.filter(
                Q(embedding__isnull=True) | Q(block_type=ContentBlock.IMAGE, image_description='')
            )

        total = blocks.count()
        if not total:
            self.stdout.write('Nada para indexar.')
            return

        ok, failed, skipped = 0, 0, 0
        for block in blocks:
            has_image_to_process = block.block_type == ContentBlock.IMAGE and block.file
            if not chatbot.block_index_text(block) and not has_image_to_process:
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
