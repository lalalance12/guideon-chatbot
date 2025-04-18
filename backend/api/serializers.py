from rest_framework import serializers
from django.contrib.auth.models import User

class UserSerializer(serializers.ModelSerializer):
    fullName = serializers.CharField(source='first_name', required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'fullName']
        extra_kwargs = {
            'password': {'write_only': True, 'required': True},
            'username': {'required': False}
        }

    def create(self, validated_data):
        # Extract first_name from validated_data
        first_name = validated_data.pop('first_name', '')
        email = validated_data.pop('email')
        
        # Create user with email as username
        user = User.objects.create_user(
            username=email,
            email=email,
            first_name=first_name,
            **validated_data
        )
        return user