from django.shortcuts import render
from django.contrib.auth.models import User
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer, ChatRequestSerializer, ChatResponseSerializer, ChatSerializer, MessageSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny
from .services import query_ollama
from .models import Chat, Message

# Create logger
logger = logging.getLogger(__name__)

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