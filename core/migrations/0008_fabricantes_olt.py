from django.db import migrations

# Compatibilidade OLT → ONU usada no Gerador de Script SA (editável no painel).
FABRICANTES = [
    ('ZTE', 'ZG', ''),
    ('Nokia', 'ZN', ''),
    ('Zhone', 'ZN 110B', ''),
    ('Fiberhome', 'FH', ''),
    ('Huawei', 'HW', 'OLT Huawei é legado: necessário validação extra do equipamento.'),
]


def criar(apps, schema_editor):
    FabricanteOLT = apps.get_model('core', 'FabricanteOLT')
    for nome, onu, aviso in FABRICANTES:
        FabricanteOLT.objects.get_or_create(nome=nome, defaults={'onu': onu, 'aviso': aviso})


class Migration(migrations.Migration):
    dependencies = [('core', '0007_olts')]
    operations = [migrations.RunPython(criar, migrations.RunPython.noop)]
