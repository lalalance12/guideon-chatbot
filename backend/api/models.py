# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\models.py
from django.db import models
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
