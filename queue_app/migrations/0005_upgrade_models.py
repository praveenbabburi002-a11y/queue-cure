from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('queue_app', '0004_patient_priority_rank'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        # QueueSettings additions
        migrations.AddField(
            model_name='queuesettings',
            name='queue_paused_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='queuesettings',
            name='clinic_name',
            field=models.CharField(default='Queue Cure Clinic', max_length=120),
        ),
        migrations.AddField(
            model_name='queuesettings',
            name='doctor_name',
            field=models.CharField(default='Dr. Attending', max_length=120),
        ),

        # Patient additions
        migrations.AddField(
            model_name='patient',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='patient',
            name='registered_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='registered_patients',
                to='auth.user',
            ),
        ),
        # Alter status to add 'skipped' choice (MySQL accepts this without column change)
        migrations.AlterField(
            model_name='patient',
            name='status',
            field=models.CharField(
                choices=[
                    ('waiting', 'Waiting'),
                    ('serving', 'Serving'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('skipped', 'Skipped'),
                ],
                default='waiting',
                max_length=20,
            ),
        ),

        # DailyStatistics additions
        migrations.AddField(
            model_name='dailystatistics',
            name='patients_skipped',
            field=models.IntegerField(default=0),
        ),

        # New QueueActionLog table
        migrations.CreateModel(
            name='QueueActionLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(
                    choices=[
                        ('register', 'Patient Registered'),
                        ('call_next', 'Called Next'),
                        ('complete', 'Completed'),
                        ('cancel', 'Cancelled'),
                        ('skip', 'Skipped'),
                        ('pause_queue', 'Queue Paused'),
                        ('resume_queue', 'Queue Resumed'),
                        ('settings_changed', 'Settings Changed'),
                    ],
                    max_length=30,
                )),
                ('description', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='queue_app.patient',
                )),
                ('performed_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='auth.user',
                )),
            ],
            options={'ordering': ['-timestamp']},
        ),
    ]
