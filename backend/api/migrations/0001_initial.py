import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import pgvector.django
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Create Chat model
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chats', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        
        # Create Course model
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('provider', models.CharField(max_length=100)),
                ('url', models.URLField()),
                ('metadata', models.JSONField(default=dict)),
            ],
        ),
        
        # Create KnowledgeSource model
        migrations.CreateModel(
            name='KnowledgeSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('source_type', models.CharField(max_length=50)),
                ('metadata', models.JSONField(default=dict)),
            ],
        ),
        
        # Create LearningPathway model
        migrations.CreateModel(
            name='LearningPathway',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(default='Learning Pathway', max_length=255)),
                ('description', models.TextField(blank=True, null=True)),
                ('metadata', models.JSONField(default=dict)),
                ('embedding', pgvector.django.VectorField(dimensions=1024)),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True)),
                ('user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='learning_pathways', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        
        # Create KnowledgeChunk model
        migrations.CreateModel(
            name='KnowledgeChunk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('metadata', models.JSONField(default=dict)),
                ('embedding', pgvector.django.VectorField(dimensions=1024)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chunks', to='api.knowledgesource')),
            ],
        ),
        
        # Create Message model
        migrations.CreateModel(
            name='Message',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('role', models.CharField(max_length=50)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='api.chat')),
            ],
        ),
        
        # Create Junction tables
        migrations.CreateModel(
            name='PathwayCourse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.IntegerField(default=0)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.course')),
                ('pathway', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.learningpathway')),
            ],
            options={
                'unique_together': {('pathway', 'course')},
            },
        ),
        
        migrations.CreateModel(
            name='PathwayKnowledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chunk', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.knowledgechunk')),
                ('pathway', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.learningpathway')),
            ],
            options={
                'unique_together': {('pathway', 'chunk')},
            },
        ),
        
        migrations.CreateModel(
            name='UserLearnedCourse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('learned_at', models.DateTimeField(auto_now_add=True)),
                ('skill_text', models.TextField(blank=True, null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learners', to='api.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learned_courses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'course')},
            },
        ),
        
        migrations.CreateModel(
            name='CourseSearch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.TextField()),
                ('searched_at', models.DateTimeField(auto_now_add=True)),
                ('chat', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_searches', to='api.chat')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='searches', to='api.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_searches', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        
        # Set up many-to-many relationships
        migrations.AddField(
            model_name='knowledgechunk',
            name='pathways',
            field=models.ManyToManyField(through='api.PathwayKnowledge', to='api.learningpathway'),
        ),
        migrations.AddField(
            model_name='course',
            name='learners',
            field=models.ManyToManyField(through='api.UserLearnedCourse', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='course',
            name='pathways',
            field=models.ManyToManyField(through='api.PathwayCourse', to='api.learningpathway'),
        ),
    ]