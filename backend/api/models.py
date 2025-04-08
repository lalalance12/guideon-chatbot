from django.db import models
from pgvector.django import VectorField

class Pathway(models.Model):
    text = models.TextField()
    metadata = models.JSONField()
    embedding = VectorField(dimensions=4096)
    
    def __str__(self):
        return f"Pathway {self.id}"