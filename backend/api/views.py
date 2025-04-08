from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserSerializer, PathwayQuerySerializer, PathwayResponseSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .utils.generate_pathways import generate_learning_pathway

# Existing views
class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

# Add this new view
class PathwayGeneratorView(APIView):
    """
    API endpoint to generate learning pathways based on user queries
    """
    permission_classes = [AllowAny]  # Or [IsAuthenticated] if you want to require authentication
    
    def post(self, request):
        serializer = PathwayQuerySerializer(data=request.data)
        if serializer.is_valid():
            query = serializer.validated_data['query']
            
            # Generate the learning pathway using your existing function
            result = generate_learning_pathway(query)
            
            # Return the response
            return Response(result)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)