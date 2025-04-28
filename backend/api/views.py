from django.shortcuts import render
from django.contrib.auth.models import User
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import UserSerializer, ChatRequestSerializer, ChatResponseSerializer, ChatSerializer, MessageSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
from .course_scraper import get_courses
import logging

logger = logging.getLogger(__name__)
from .services import query_ollama
from .models import Chat, Message

# Create logger
logger = logging.getLogger(__name__)

# Create your views here.

class CreateUserView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable authentication for registration

    def create(self, request, *args, **kwargs):
        try:
            logger.info(f"Registration attempt with data: {request.data}")
            
            # Extract and validate required fields
            email = request.data.get('email')
            password = request.data.get('password')
            fullName = request.data.get('fullName')

            if not all([email, password, fullName]):
                logger.warning("Missing required fields in registration request")
                return Response(
                    {"error": "Email, password, and full name are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if user already exists
            if User.objects.filter(email=email).exists():
                logger.warning(f"Registration attempt with existing email: {email}")
                return Response(
                    {"error": "User with this email already exists"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create user data for serializer
            user_data = {
                'email': email,
                'password': password,
                'fullName': fullName  # This will be mapped to first_name by the serializer
            }

            serializer = self.get_serializer(data=user_data)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            
            logger.info(f"Successfully created user: {user.email}")
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            
            # Prepare response data
            response_data = {
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'fullName': user.first_name
                },
                'token': str(refresh.access_token)
            }
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}", exc_info=True)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'id': user.id,
            'email': user.email,
            'fullName': user.first_name
        })

class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Disable authentication for login

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {"error": "Please provide both email and password"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Try to find user by email
        try:
            user = User.objects.get(email=email)
            if user.check_password(password):
                refresh = RefreshToken.for_user(user)
                return Response({
                    'user': {
                        'id': user.id,
                        'email': user.email,
                        'fullName': user.first_name
                    },
                    'token': str(refresh.access_token)
                })
            else:
                return Response(
                    {"error": "Invalid password"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED
            )

class CourseSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {"error": "Please provide a search query using the 'q' parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        result = get_courses(query)
        if "error" in result:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(result, status=status.HTTP_200_OK)

class ChatView(APIView):
    """
    API endpoint for chat interactions with Ollama model
    """
    permission_classes = [AllowAny]  # Can be changed to IsAuthenticated if needed

    def post(self, request):
        logger.info(f"Received chat request: {request.data}")
        serializer = ChatRequestSerializer(data=request.data)
        if serializer.is_valid():
            prompt = serializer.validated_data['prompt']
            chat_id = serializer.validated_data.get('chat_id')
            
            logger.info(f"Processing chat request - Prompt: '{prompt}', Chat ID: {chat_id}")
            
            # Get or create chat session
            chat = None
            if chat_id:
                try:
                    chat = Chat.objects.get(id=chat_id)
                    logger.info(f"Found existing chat with ID: {chat_id}")
                except Chat.DoesNotExist:
                    logger.warning(f"Chat ID {chat_id} not found, creating new chat")
                    chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
            else:
                logger.info("No chat_id provided, creating new chat")
                chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
            
            logger.info(f"Using chat with ID: {chat.id}")
            
            # Save user message
            user_message = Message.objects.create(
                chat=chat,
                role='user',
                content=prompt
            )
            logger.info(f"Saved user message with ID: {user_message.id}")
            
            # Get response from Ollama service
            logger.info(f"Querying Ollama with chat_id: {chat.id}")
            response_text = query_ollama(prompt, chat.id)
            
            # Save assistant response
            assistant_message = Message.objects.create(
                chat=chat,
                role='assistant',
                content=response_text
            )
            logger.info(f"Saved assistant message with ID: {assistant_message.id}")
            
            # Get all messages in this chat for debugging
            all_messages = Message.objects.filter(chat=chat).order_by('timestamp')
            logger.info(f"All messages in chat {chat.id}:")
            for idx, msg in enumerate(all_messages):
                logger.info(f"  {idx+1}. {msg.role}: {msg.content[:50]}{'...' if len(msg.content) > 50 else ''}")
            
            # Return the response
            response_data = {
                'response': response_text,
                'chat_id': chat.id
            }
            logger.info(f"Returning response with chat_id: {chat.id}")
            response_serializer = ChatResponseSerializer(data=response_data)
            response_serializer.is_valid()
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        logger.error(f"Invalid request data: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ChatHistoryView(APIView):
    """
    API endpoint for retrieving chat history
    """
    permission_classes = [AllowAny]  # Can be changed to IsAuthenticated if needed
    
    def get(self, request, chat_id=None):
        logger.info(f"Chat history request - Chat ID: {chat_id}")
        if chat_id:
            try:
                chat = Chat.objects.get(id=chat_id)
                serializer = ChatSerializer(chat)
                logger.info(f"Retrieved chat with ID: {chat_id}, message count: {chat.messages.count()}")
                return Response(serializer.data)
            except Chat.DoesNotExist:
                logger.warning(f"Chat with ID {chat_id} not found")
                return Response({"error": "Chat not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Return list of chats for the user
            chats = Chat.objects.all()
            if request.user.is_authenticated:
                chats = chats.filter(user=request.user)
            serializer = ChatSerializer(chats, many=True)
            logger.info(f"Retrieved {chats.count()} chats")
            return Response(serializer.data)