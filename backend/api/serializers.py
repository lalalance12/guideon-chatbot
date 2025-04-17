from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Chat, Message

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'first_name', 'last_name']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

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