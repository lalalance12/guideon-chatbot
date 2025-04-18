# filepath: c:\Users\Asus\Desktop\guideon-chatbot\backend\api\views.py
from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Updated serializer imports
from .serializers import UserSerializer, PathwayQuerySerializer, ContextResponseSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
# Import the vector search function
from .utils.query_vectors import search_similar_content
# Removed unused import: from .utils.generate_pathways import generate_learning_pathway

# Existing views
class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]

# Renamed and modified view
class ContextRetrieverView(APIView):
    """
    API endpoint to retrieve relevant context (skills, roles, etc.)
    from the knowledge base based on user queries using vector similarity search.
    """
    permission_classes = [AllowAny]  # Or [IsAuthenticated]

    def post(self, request):
        serializer = PathwayQuerySerializer(data=request.data)
        if serializer.is_valid():
            query = serializer.validated_data['query']
            limit = serializer.validated_data.get('limit', 5) # Get limit from serializer

            # Perform vector search to find relevant context
            # search_similar_content should return a list of dicts or an error dict
            context_results = search_similar_content(query, limit=limit)

            # Check if the search function returned an error
            if isinstance(context_results, dict) and "error" in context_results:
                # Return a server error or a specific error message
                return Response(
                    {"error": f"Failed to retrieve context: {context_results['error']}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            # Prepare the response data using the new serializer
            response_data = {
                "query": query,
                "context": context_results,
                "count": len(context_results)
            }
            response_serializer = ContextResponseSerializer(data=response_data)

            # Validate the response structure (good practice)
            if response_serializer.is_valid():
                 return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                 # Log the serializer error for debugging
                 print(f"ContextResponseSerializer errors: {response_serializer.errors}")
                 return Response(
                     {"error": "Internal server error formatting response."},
                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
                 )

        # Return validation errors if the query serializer is invalid
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
