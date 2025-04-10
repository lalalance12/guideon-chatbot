from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, ChatRequestSerializer, ChatResponseSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .services import query_ollama

# Create your views here.

class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

class ChatView(APIView):
    """
    API endpoint for chat interactions with Ollama model
    """
    permission_classes = [AllowAny]  # Can be changed to IsAuthenticated if needed

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        if serializer.is_valid():
            prompt = serializer.validated_data['prompt']
            
            # Get response from Ollama service
            response_text = query_ollama(prompt)
            
            # Return the response
            response_serializer = ChatResponseSerializer(data={'response': response_text})
            response_serializer.is_valid()
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)