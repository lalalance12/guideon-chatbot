# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\serializers.py
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Pathway # Import Pathway if needed for context structure validation (optional)
from django.contrib.auth.password_validation import validate_password
from .models import Chat, Message

class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='first_name', required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'fullName']
        extra_kwargs = {
            'username': {'required': False}  
        }

    def create(self, validated_data):
        # Extract first_name from validated_data
        first_name = validated_data.pop('first_name', '')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        
        # Create user with email as username
        user = User.objects.create_user(
            username=email,  # Use email as username
            email=email,
            first_name=first_name,
            password=password
        )
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


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'role', 'content', 'timestamp']

class ChatSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = Chat
        fields = ['id', 'title', 'user', 'created_at', 'updated_at', 'messages']

class ChatRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True)
    chat_id = serializers.IntegerField(required=False)

class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    chat_id = serializers.IntegerField()