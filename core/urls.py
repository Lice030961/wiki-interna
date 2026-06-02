from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('busca/', views.search, name='search'),

    # Layers 2 & 3
    path('topico/<slug:major_slug>/', views.major_topic, name='major_topic'),
    path('topico/<slug:major_slug>/<slug:minor_slug>/', views.minor_topic, name='minor_topic'),

    # Admin topic management
    path('admin-wiki/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-wiki/topico/criar/', views.admin_major_topic_create, name='admin_major_topic_create'),
    path('admin-wiki/topico/<slug:major_slug>/editar/', views.admin_major_topic_edit, name='admin_major_topic_edit'),
    path('admin-wiki/topico/<slug:major_slug>/excluir/', views.admin_major_topic_delete, name='admin_major_topic_delete'),
    path('admin-wiki/topico/<slug:major_slug>/sub/criar/', views.admin_minor_topic_create, name='admin_minor_topic_create'),
    path('admin-wiki/topico/<slug:major_slug>/sub/<slug:minor_slug>/editar/', views.admin_minor_topic_edit, name='admin_minor_topic_edit'),
    path('admin-wiki/topico/<slug:major_slug>/sub/<slug:minor_slug>/excluir/', views.admin_minor_topic_delete, name='admin_minor_topic_delete'),

    # Admin content blocks
    path('admin-wiki/topico/<slug:major_slug>/sub/<slug:minor_slug>/conteudo/', views.admin_content_edit, name='admin_content_edit'),
    path('admin-wiki/topico/<slug:major_slug>/sub/<slug:minor_slug>/bloco/adicionar/', views.admin_block_add, name='admin_block_add'),
    path('admin-wiki/bloco/<int:block_id>/editar/', views.admin_block_edit, name='admin_block_edit'),
    path('admin-wiki/bloco/<int:block_id>/excluir/', views.admin_block_delete, name='admin_block_delete'),

    # Reordenação via drag-and-drop
    path('admin-wiki/bloco/reordenar/', views.admin_block_reorder, name='admin_block_reorder'),
    path('admin-wiki/topico/reordenar/', views.admin_major_topic_reorder, name='admin_major_topic_reorder'),
    path('admin-wiki/topico/<slug:major_slug>/sub/reordenar/', views.admin_minor_topic_reorder, name='admin_minor_topic_reorder'),

    # Glossário
    path('admin-wiki/glossario/', views.admin_glossary, name='admin_glossary'),
    path('admin-wiki/glossario/salvar/', views.admin_glossary_save, name='admin_glossary_save'),
    path('admin-wiki/glossario/lista/', views.admin_glossary_list, name='admin_glossary_list'),
    path('admin-wiki/glossario/<int:term_id>/excluir/', views.admin_glossary_delete, name='admin_glossary_delete'),
]