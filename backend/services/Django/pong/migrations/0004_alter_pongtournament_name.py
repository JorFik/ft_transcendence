# Generated by Django 5.1.6 on 2025-02-23 15:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pong', '0003_alter_pongmatch_status_pongtournament_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pongtournament',
            name='name',
            field=models.CharField(max_length=100),
        ),
    ]
