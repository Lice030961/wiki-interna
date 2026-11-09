"""Testes do servidor. Rodar: python manage.py test core

O chatbot (Cloudflare Workers AI) é sempre substituído por mock: os testes nunca chamam a rede.
O parser do Gerador SA tem testes próprios em Node: node --test tests_js/
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContentBlock, FabricanteOLT, GlossaryTerm, MajorTopic, MinorTopic, OLT, ProjetoGPON
from . import ratelimit
from .views import apply_glossary, city_key, olt_data, projeto_key
from .views.admin_olts import _split_projeto

PASSWORD = 'senha-de-teste-123'


class Base(TestCase):
    def setUp(self):
        cache.clear()
        # Nenhum teste chama o Workers AI.
        patcher = mock.patch('core.chatbot.update_block_embedding')
        self.embed = patcher.start()
        self.addCleanup(patcher.stop)
        self.admin = get_user_model().objects.create_user('chefe', password=PASSWORD, is_staff=True)
        self.major = MajorTopic.objects.create(title='Fluxo de Atendimento', icon='📞')
        self.minor = MinorTopic.objects.create(major_topic=self.major, title='Abrir SA')
        ContentBlock.objects.create(minor_topic=self.minor, block_type='text', content='Use o **SIS**.')


# ── Infra ─────────────────────────────────────────────────────────────────────

class HealthzTests(Base):
    def test_responde_sem_tocar_no_banco(self):
        # O monitor pinga esta URL 24h: se consultar o banco, o Neon nunca dorme e a cota acaba.
        with self.assertNumQueries(0):
            r = self.client.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'ok')

    def test_html_vai_comprimido(self):
        r = self.client.get('/', HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(r.get('Content-Encoding'), 'gzip')


# ── Páginas públicas ──────────────────────────────────────────────────────────

class PublicPagesTests(Base):
    def test_paginas_sem_login(self):
        for url in ['/', f'/topico/{self.major.slug}/', f'/topico/{self.major.slug}/{self.minor.slug}/',
                    '/ferramentas/gerador-sa/', '/ferramentas/batimento/', '/login/']:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_topico_inexistente_404(self):
        self.assertEqual(self.client.get('/topico/nao-existe/').status_code, 404)
        self.assertEqual(self.client.get(f'/topico/{self.major.slug}/nao-existe/').status_code, 404)

    def test_bloco_de_texto_renderiza_markdown(self):
        r = self.client.get(f'/topico/{self.major.slug}/{self.minor.slug}/')
        self.assertContains(r, '<strong>SIS</strong>', html=False)

    def test_busca_acha_topico(self):
        r = self.client.get('/busca/', {'q': 'atendimento'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any('Atendimento' in str(item) for item in r.json()['results']))

    def test_busca_vazia(self):
        self.assertEqual(self.client.get('/busca/').json(), {'results': []})

    def test_painel_exige_admin(self):
        r = self.client.get('/admin-wiki/dashboard/')
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginTests(Base):
    def post(self, password=PASSWORD, username='chefe', next_url=None, ip='10.0.0.1'):
        url = '/login/' + (f'?next={next_url}' if next_url else '')
        return self.client.post(url, {'username': username, 'password': password}, REMOTE_ADDR=ip)

    def test_login_ok_vai_ao_painel(self):
        r = self.post()
        self.assertRedirects(r, '/admin-wiki/dashboard/')

    def test_senha_errada(self):
        r = self.post(password='errada')
        self.assertContains(r, 'Credenciais inválidas')

    def test_leitor_nao_entra(self):
        get_user_model().objects.create_user('leitor', password=PASSWORD)
        r = self.post(username='leitor')
        self.assertContains(r, 'Credenciais inválidas')

    def test_next_do_proprio_site(self):
        r = self.post(next_url='/admin-wiki/olts/')
        self.assertRedirects(r, '/admin-wiki/olts/')

    def test_next_externo_nao_redireciona(self):
        r = self.post(next_url='https://exemplo.com/phishing')
        self.assertRedirects(r, '/admin-wiki/dashboard/')

    def test_bloqueia_por_ip(self):
        for _ in range(ratelimit.LOGIN_MAX_FALHAS_IP):
            self.post(password='errada', username=f'x{_}')
        # Mesmo com a senha certa, o IP está bloqueado.
        r = self.post()
        self.assertContains(r, 'Muitas tentativas')

    def test_bloqueia_por_usuario_mesmo_trocando_ip(self):
        for i in range(ratelimit.LOGIN_MAX_FALHAS_USUARIO):
            self.post(password='errada', ip=f'10.0.1.{i}')
        r = self.post(ip='10.0.2.1')
        self.assertContains(r, 'Muitas tentativas')

    def test_acerto_zera_contador(self):
        for _ in range(ratelimit.LOGIN_MAX_FALHAS_IP - 1):
            self.post(password='errada')
        self.assertRedirects(self.post(), '/admin-wiki/dashboard/')
        self.client.logout()
        self.post(password='errada')
        self.assertRedirects(self.post(), '/admin-wiki/dashboard/')


# ── Chat ──────────────────────────────────────────────────────────────────────

@mock.patch('core.chatbot.answer_question', return_value={'answer': 'Resposta', 'sources': []})
class ChatTests(Base):
    def ask(self, question='Como abrir SA?', ip='10.0.0.9'):
        return self.client.post('/chat/', {'question': question}, content_type='application/json', REMOTE_ADDR=ip)

    def test_responde(self, answer):
        r = self.ask()
        self.assertEqual(r.json(), {'answer': 'Resposta', 'sources': []})
        answer.assert_called_once()

    def test_get_nao_permitido(self, answer):
        self.assertEqual(self.client.get('/chat/').status_code, 405)

    def test_pergunta_vazia(self, answer):
        self.assertEqual(self.ask('  ').status_code, 400)
        answer.assert_not_called()

    def test_json_invalido(self, answer):
        r = self.client.post('/chat/', 'não é json', content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_limite_por_minuto(self, answer):
        for _ in range(ratelimit.CHAT_MAX_POR_MINUTO):
            self.assertEqual(self.ask().status_code, 200)
        r = self.ask()
        self.assertEqual(r.status_code, 429)
        self.assertIn('error', r.json())
        self.assertEqual(answer.call_count, ratelimit.CHAT_MAX_POR_MINUTO)
        # Outro IP continua podendo perguntar.
        self.assertEqual(self.ask(ip='10.0.0.10').status_code, 200)

    def test_erro_inesperado_vira_502(self, answer):
        answer.side_effect = RuntimeError('falhou')
        with self.assertLogs('core.views.public', level='ERROR'):
            r = self.ask()
        self.assertEqual(r.status_code, 502)


# ── Uploads ───────────────────────────────────────────────────────────────────

@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class UploadTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.url = reverse('admin_block_add', args=[self.major.slug, self.minor.slug])

    def add(self, block_type, name, data=b'x'):
        return self.client.post(self.url, {'block_type': block_type, 'file': SimpleUploadedFile(name, data)}, follow=True)

    def test_imagem_aceita(self):
        self.add('image', 'foto.PNG')
        self.assertTrue(self.minor.blocks.filter(block_type='image').exists())

    def test_extensao_errada_recusada(self):
        r = self.add('image', 'pagina.html')
        self.assertContains(r, 'não aceito')
        self.assertFalse(self.minor.blocks.filter(block_type='image').exists())

    def test_video_no_bloco_de_imagem_recusado(self):
        self.add('image', 'video.mp4')
        self.assertFalse(self.minor.blocks.filter(block_type='image').exists())

    @override_settings(MAX_UPLOAD_SIZE=10)
    def test_arquivo_grande_recusado(self):
        r = self.add('video', 'aula.mp4', b'x' * 11)
        self.assertContains(r, 'muito grande')
        self.assertFalse(self.minor.blocks.filter(block_type='video').exists())

    def test_tipo_de_bloco_invalido_vira_texto(self):
        self.client.post(self.url, {'block_type': 'script', 'content': 'oi'})
        self.assertEqual(self.minor.blocks.last().block_type, 'text')


# ── Glossário / markdown ──────────────────────────────────────────────────────

class GlossaryTests(TestCase):
    def test_markdown_e_escape(self):
        html = apply_glossary('<b>x</b> **negrito** _it_ ~~r~~ `c`', [])
        self.assertIn('&lt;b&gt;', html)
        self.assertIn('<strong>negrito</strong>', html)
        self.assertIn('<em>it</em>', html)
        self.assertIn('<s>r</s>', html)
        self.assertIn('<code', html)

    def test_caixa_de_atencao(self):
        self.assertIn('attention-box', apply_glossary('[ATENÇÃO]Cuidado[/ATENÇÃO]', []))

    def test_tooltip_so_na_palavra_inteira(self):
        terms = [GlossaryTerm(term='SA', definition='Solicitação de "Atendimento"')]
        html = apply_glossary('Abrir SA na SALA', terms)
        self.assertEqual(html.count('glossary-term'), 1)
        self.assertIn('&quot;Atendimento&quot;', html)


# ── Gerador SA: dados de OLT/CTO ──────────────────────────────────────────────

class OltDataTests(TestCase):
    def test_chaves(self):
        self.assertEqual(city_key("Santa Bárbara d'Oeste"), 'santa barbara doeste')
        self.assertEqual(projeto_key('GPON Bauru Área E - LPNET'), 'bauru area e lpnet')

    def test_split_projeto(self):
        self.assertEqual(_split_projeto('GPON Bauru Area E LPNET;BRE'), ('GPON Bauru Area E LPNET', 'BRE'))
        self.assertEqual(_split_projeto('BRE\tGPON Bauru'), ('GPON Bauru', 'BRE'))
        self.assertEqual(_split_projeto('GPON Bauru BRE'), ('GPON Bauru', 'BRE'))
        self.assertIsNone(_split_projeto('sem sigla nenhuma'))

    def test_olt_data(self):
        zte = FabricanteOLT.objects.get_or_create(nome='ZTE', defaults={'onu': 'ZG'})[0]
        nokia = FabricanteOLT.objects.get_or_create(nome='Nokia', defaults={'onu': 'ZN'})[0]
        OLT.objects.create(nome='LT-G01-SUM001-SP', fabricante=zte, cidade='Sumaré')
        OLT.objects.create(nome='LT-G02-SUM002-SP', fabricante=zte, cidade='Sumare')
        OLT.objects.create(nome='LT-G01-SUM003-SP', fabricante=nokia, cidade='Sumaré')
        ProjetoGPON.objects.create(nome='GPON Bauru Area E', sigla='BRE')
        data = olt_data()
        self.assertEqual(data['olts']['LT-G01-SUM001-SP'], 'ZTE')
        self.assertEqual(data['cidades']['sumare'], {'nome': 'Sumaré', 'fabs': ['ZTE', 'Nokia']})
        self.assertEqual(data['siglas']['SUM'], ['ZTE', 'Nokia'])
        self.assertEqual(data['projetos']['bauru area e'], 'BRE')


class OltImportTests(Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_importa_csv_e_substitui(self):
        csv = 'NOME OLT;FABRICANTE;CIDADE\nLT-G01-ABC001-SP;ZTE;Abc\nLT-G01-ABC001-SP;ZTE;Abc\nLT-G01-XYZ001-SP;Marca Nova;Xyz\n'
        self.client.post('/admin-wiki/olts/importar/', {'arquivo': SimpleUploadedFile('olts.csv', csv.encode())})
        self.assertEqual(OLT.objects.count(), 2)  # duplicada entra uma vez
        self.assertEqual(FabricanteOLT.objects.get(nome='Marca Nova').onu, '?')

    def test_csv_sem_colunas(self):
        r = self.client.post('/admin-wiki/olts/importar/',
                             {'arquivo': SimpleUploadedFile('olts.csv', b'A;B\n1;2\n')}, follow=True)
        self.assertContains(r, 'CSV sem as colunas')

    def test_importa_projetos(self):
        txt = 'PROJETO;SIGLA\nGPON Bauru Area E;BRE\nlinha ruim\n'
        self.client.post('/admin-wiki/olts/projetos/importar/', {'arquivo': SimpleUploadedFile('gpon.txt', txt.encode())})
        self.assertEqual(list(ProjetoGPON.objects.values_list('sigla', flat=True)), ['BRE'])


# ── Estáticos / build de produção ─────────────────────────────────────────────

class StaticTests(Base):
    def test_sem_cdn_nas_paginas(self):
        # Tudo servido pelo próprio site: funciona num servidor interno sem internet.
        self.client.force_login(self.admin)
        for url in ['/', '/login/', '/ferramentas/gerador-sa/', '/ferramentas/batimento/', '/admin-wiki/dashboard/',
                    reverse('admin_content_edit', args=[self.major.slug, self.minor.slug])]:
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                for cdn in ('cdn.tailwindcss.com', 'fonts.googleapis.com', 'cdn.jsdelivr.net', 'cdnjs.cloudflare.com'):
                    self.assertNotIn(cdn, html)

    def test_gerador_carrega_parser_antes(self):
        html = self.client.get('/ferramentas/gerador-sa/').content.decode()
        self.assertLess(html.index('js/sa_parser.js'), html.index('js/script_generator.js'))

    def test_collectstatic_de_producao(self):
        # O build do Render roda collectstatic com o storage de manifest, que falha se um CSS/JS
        # aponta para um arquivo inexistente (ex.: "sourceMappingURL" de biblioteca em static/vendor/).
        import tempfile
        from io import StringIO
        from django.core.management import call_command
        with tempfile.TemporaryDirectory() as root, override_settings(STATIC_ROOT=root, STORAGES={
            'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
        }):
            call_command('collectstatic', interactive=False, verbosity=0, stdout=StringIO())
