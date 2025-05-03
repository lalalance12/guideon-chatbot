# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\models.py
from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField

class Pathway(models.Model):
    text = models.TextField()
    metadata = models.JSONField()
    # Ensure 'dimensions' matches the output dimension of your embedding model (e.g., bge-m3 often uses 1024).
    # Mismatch can cause errors during storage or querying.
    embedding = VectorField(dimensions=1024)

    def __str__(self):
        # Provide a more informative string representation``
        title = self.metadata.get('title', 'Unknown')
        type = self.metadata.get('type', 'Pathway')
        return f"{type.capitalize()}: {title[:50]}... (ID: {self.id})"

    class Meta:
        # Add indexes for potential filtering optimization
        indexes = [
            models.Index(fields=['metadata']),
        ]
class Chat(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255, default="New Chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Chat {self.id}: {self.title}"

class Message(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]
    
    chat = models.ForeignKey(Chat, related_name='messages', on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.role} message in chat {self.chat.id}"
