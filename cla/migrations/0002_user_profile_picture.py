# Generated by Django 4.2.19 on 2025-02-24 21:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cla', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='profile_picture',
            field=models.ImageField(blank=True, default='profilepics/default.jpg', null=True, upload_to='profilepics/'),
        ),
    ]
