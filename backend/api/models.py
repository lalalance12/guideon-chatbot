from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField
import uuid

class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='chats')
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Chat {self.id}: {self.title}"

class Message(models.Model):
    content = models.TextField()
    role = models.CharField(max_length=50)  # 'user', 'assistant', 'system'
    timestamp = models.DateTimeField(auto_now_add=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    embedding = VectorField(dimensions=1024, null=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.role} message in chat {self.chat.id}"

class Course(models.Model):
    title = models.CharField(max_length=255)
    provider = models.CharField(max_length=100)
    url = models.URLField()
    description = models.TextField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    metadata = models.JSONField(default=dict)      
    learners = models.ManyToManyField(User, through='UserLearnedCourse')
    
    def __str__(self):
        return f"{self.title} by {self.provider}"

class CourseSearch(models.Model):
    query = models.TextField()
    searched_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='course_searches')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='searches')
    chat = models.ForeignKey(Chat, on_delete=models.SET_NULL, null=True, blank=True, related_name='course_searches')
    
    def __str__(self):
        return f"Search for '{self.query[:30]}...' by {self.user.username}"

class LearningPathway(models.Model):
    title = models.CharField(max_length=255, default='Learning Pathway')
    description = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    embedding = VectorField(dimensions=1024)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name='learning_pathways')
    
    def __str__(self):
        return f"{self.title} (ID: {self.id})"
    
    class Meta:
        indexes = [
            models.Index(fields=['metadata']),
        ]

class KnowledgeSource(models.Model):
    name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=50)
    metadata = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.name} ({self.source_type})"

class KnowledgeChunk(models.Model):
    text = models.TextField()
    metadata = models.JSONField(default=dict)
    embedding = VectorField(dimensions=1024) # Ensure this matches your embedding model's dimensions
    source = models.ForeignKey(KnowledgeSource, on_delete=models.CASCADE, related_name='chunks')
    category = models.CharField(max_length=100, db_index=True, null=True, blank=True) # Added category field
    pathways = models.ManyToManyField(LearningPathway, through='PathwayKnowledge')
    
    def __str__(self):
        return f"Chunk {self.id} ({self.category}) from {self.source.name}"

class PathwayCourse(models.Model):
    pathway = models.ForeignKey(LearningPathway, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)  # For ordering courses in a pathway
    
    class Meta:
        unique_together = ('pathway', 'course')
    
    def __str__(self):
        return f"{self.course.title} in {self.pathway.title}"

class PathwayKnowledge(models.Model):
    pathway = models.ForeignKey(LearningPathway, on_delete=models.CASCADE)
    chunk = models.ForeignKey(KnowledgeChunk, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('pathway', 'chunk')
    
    def __str__(self):
        return f"Knowledge link: {self.pathway.title} - Chunk {self.chunk.id}"

class UserLearnedCourse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='learned_courses')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='learned_courses') 
    learned_at = models.DateTimeField(auto_now_add=True)
    skill_text = models.TextField(null=True, blank=True)  # Text description of skills gained
    
    class Meta:
        unique_together = ('user', 'course')
    
    def __str__(self):
        return f"{self.user.username} learned {self.course.title}"