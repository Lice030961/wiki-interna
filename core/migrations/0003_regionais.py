from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_glossaryterm'),
    ]

    operations = [
        migrations.AddField(
            model_name='minortopic',
            name='is_territory_map',
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name='Regiao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200)),
                ('order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'ordering': ['order', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='Territorio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200)),
                ('order', models.PositiveIntegerField(default=0)),
                ('regiao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='territorios', to='core.regiao')),
            ],
            options={
                'ordering': ['order', 'nome'],
            },
        ),
        migrations.CreateModel(
            name='Cidade',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=200)),
                ('territorio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cidades', to='core.territorio')),
            ],
            options={
                'ordering': ['nome'],
            },
        ),
    ]
