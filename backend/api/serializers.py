# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Pathway # Import Pathway if needed for context structure validation (optional)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password']
        extra_kwargs = {'password': {'write_only': True, 'required': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class PathwayQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=True, help_text="The career, skill, or general query")
    limit = serializers.IntegerField(required=False, default=5, min_value=1, max_value=50, help_text="Maximum number of relevant context items to return")


# Renamed and modified for returning context
class ContextResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    # Removed 'pathway' field
    context = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of relevant context items found via vector search"
    )
    # Optionally add a count or other metadata about the response
    count = serializers.IntegerField(help_text="Number of context items returned")
