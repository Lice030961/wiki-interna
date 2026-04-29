import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dotenv import load_dotenv
from core.models import MajorTopic, MinorTopic

load_dotenv()


class Command(BaseCommand):
    help = 'Seed initial users and topics from topicos.txt structure'

    def handle(self, *args, **kwargs):
        self._create_users()
        self._create_topics()
        self.stdout.write(self.style.SUCCESS('Seed concluído com sucesso!'))

    def _create_users(self):
        admin_user = os.getenv('ADMIN_USERNAME', 'admin')
        admin_pass = os.getenv('ADMIN_PASSWORD', 'admin123')

        if not User.objects.filter(username=admin_user).exists():
            User.objects.create_superuser(username=admin_user, password=admin_pass, email='')
            self.stdout.write(f'  Admin "{admin_user}" criado.')
        else:
            self.stdout.write(f'  Admin "{admin_user}" já existe.')

    def _create_topics(self):
        topics = [
            {
                'title': 'Fluxo de Atendimento',
                'icon': '🔄',
                'description': 'Como identificar e encaminhar cada atendimento',
                'minor': [
                    ('Localizar Cliente', '🔍', 'Como localizar o cliente no sistema'),
                    ('Identificar Solicitação', '🧠', 'Como identificar o tipo de solicitação'),
                ],
            },
            {
                'title': 'Tipos de Atendimento',
                'icon': '📌',
                'description': 'Fluxos específicos para cada tipo de chamado',
                'minor': [
                    ('Manutenção', '🛠️', 'Fluxo completo de atendimento de manutenção'),
                    ('Massiva', '🚨', 'Como tratar ocorrências de massiva'),
                    ('Instalação', '🏗️', 'Procedimento de instalação'),
                    ('Mudança de Plano', '🔄', 'Como processar mudança de plano'),
                    ('Mudança de Ponto', '📍', 'Como processar mudança de ponto'),
                    ('Requisições', '⚙️', 'Fluxo de requisições e acionamento NOC'),
                    ('Telefonia', '☎️', 'Atendimento ATA e VOIP'),
                ],
            },
            {
                'title': 'Tutoriais Rápidos',
                'icon': '📄',
                'description': 'Passo a passo para as tarefas mais comuns',
                'minor': [
                    ('Como Localizar Cliente', '🔍', 'Passo a passo para localizar cliente no SIS'),
                    ('Como Criar SA', '📝', 'Passo a passo para abertura de SA'),
                    ('Erros ao Abrir SA', '⚠️', 'Principais erros e como resolver'),
                    ('Como Abrir GLPI', '🖥️', 'Passo a passo para abrir chamado no GLPI'),
                    ('Identificar Problema', '🔎', 'Como identificar a origem do problema'),
                ],
            },
            {
                'title': 'Glossário',
                'icon': '📚',
                'description': 'Siglas e termos utilizados no sistema',
                'minor': [
                    ('Siglas do Sistema', '🔤', 'Significado das siglas SA, INC, GLPI, NOC e outras'),
                ],
            },
        ]

        for i, t in enumerate(topics):
            major, created = MajorTopic.objects.get_or_create(
                title=t['title'],
                defaults={'icon': t['icon'], 'description': t['description'], 'order': i},
            )
            status = 'criado' if created else 'já existe'
            self.stdout.write(f'  Tópico principal "{major.title}" {status}.')

            for j, (mt_title, mt_icon, mt_desc) in enumerate(t['minor']):
                minor, mc = MinorTopic.objects.get_or_create(
                    major_topic=major,
                    title=mt_title,
                    defaults={'icon': mt_icon, 'description': mt_desc, 'order': j},
                )
                ms = 'criado' if mc else 'já existe'
                self.stdout.write(f'    Sub-tópico "{minor.title}" {ms}.')
