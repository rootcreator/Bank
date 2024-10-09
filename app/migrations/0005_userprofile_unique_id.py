# Generated by Django 5.0.3 on 2024-10-09 03:47

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0004_remove_userprofile_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='unique_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
