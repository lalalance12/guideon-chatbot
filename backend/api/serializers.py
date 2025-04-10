from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

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

class ChatRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(required=True)

class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()