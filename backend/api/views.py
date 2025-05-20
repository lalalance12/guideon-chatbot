import json
from django.shortcuts import render
from django.contrib.auth.models import User
import logging
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
# Updated serializer imports
from .serializers import (UserSerializer, ChatRequestSerializer, ChatResponseSerializer, ChatSerializer, MessageSerializer, PathwayQuerySerializer, ContextResponseSerializer, 
    CourseSerializer, CourseSearchSerializer, LearningPathwaySerializer,
    KnowledgeSourceSerializer, KnowledgeChunkSerializer)
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import authenticate
import asyncio
from .agents.course_search_agent import CourseSearchAgent
logger = logging.getLogger(__name__)
from .services import query_ollama
from .models import Chat, Message, Course, CourseSearch, LearningPathway, KnowledgeSource, KnowledgeChunk
from api.utils.intent_classifier import QueryIntent, classify_intent

# Create logger
logger = logging.getLogger(__name__)
# Import the vector search function
from .utils.query_vectors import search_similar_content
# Removed unused import: from .utils.generate_pathways import generate_learning_pathway

# Existing views
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

class SemanticCourseSearchView(APIView):
    """
    API endpoint for semantic course search using only a query and context.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query = request.data.get('query')
        context = request.data.get('context', {})

        if not query:
            return Response({'error': 'query is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Use the CourseSearchAgent directly with the provided context
            agent = CourseSearchAgent()
            import asyncio
            result = asyncio.run(agent.process(query, context))

            return Response(result)

        except Exception as e:
            logger.error(f"Error in semantic course search: {str(e)}")
            return Response(
                {"error": f"Failed to search for courses: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ChatView(APIView):
    """
    API endpoint for chat interactions with Ollama model
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info(f"Received chat request: {request.data}")
        serializer = ChatRequestSerializer(data=request.data)
        if serializer.is_valid():
            prompt = serializer.validated_data['prompt']
            chat_id = serializer.validated_data.get('chat_id')
            
            # Get or create chat session
            chat = None
            if chat_id:
                try:
                    chat = Chat.objects.get(id=chat_id)
                    logger.info(f"Found existing chat with ID: {chat_id}")
                    
                    # Check if the message has content before saving
                    if prompt.strip():  # Only save non-empty messages
                        user_message = Message.objects.create(
                            chat=chat,
                            role='user',
                            content=prompt
                        )
                        logger.debug(f"Saved user message with content length: {len(prompt)}")
                    else:
                        logger.warning("Empty user message detected - not saving to database")
                except Chat.DoesNotExist:
                    logger.warning(f"Chat ID {chat_id} not found, creating new chat")
                    chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
            else:
                logger.info("No chat_id provided, creating new chat")
                chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
                
            logger.info(f"Using chat with ID: {chat.id}")
            
            try:
                # Save the user message
                user_message = Message.objects.create(
                    chat=chat,
                    role='user',
                    content=prompt
                )
                
                # Get chat history for context
                chat_history = Message.objects.filter(chat=chat).order_by('-timestamp')[:10]
                formatted_history = []
                for msg in chat_history:
                    if msg.id != user_message.id:  # Skip the current message
                        formatted_history.append({
                            "is_user": msg.role == 'user',
                            "text": msg.content,
                            "timestamp": msg.timestamp.isoformat()
                        })
                
                # Check if we're expecting a topic selection
                topics = []
                awaiting_selection = False
                if hasattr(chat, 'metadata') and chat.metadata:
                    try:
                        metadata = json.loads(chat.metadata) if isinstance(chat.metadata, str) else chat.metadata
                        if isinstance(metadata, dict) and metadata.get('awaiting_topic_selection') and metadata.get('topics'):
                            topics = metadata.get('topics', [])
                            awaiting_selection = True
                            logger.info(f"User is responding to topic selection from: {topics}")
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse chat metadata JSON: {chat.metadata}")
                
                # Initialize the orchestrator agent with context
                context = {
                    'chat_id': str(chat.id),
                    'chat_history': formatted_history,
                }
                
                # Add topics to context if we're awaiting selection
                if awaiting_selection:
                    context['multiple_topics'] = topics
                
                # Use orchestrator agent to handle the query with all available agents
                from .agents.orchestrator_agent import OrchestratorAgent
                orchestrator = OrchestratorAgent()
                
                # Process the query with the orchestrator
                orchestrator_result = asyncio.run(orchestrator.process(prompt, context))
                
                # Extract intent information from orchestration result
                intent = orchestrator_result.get('metadata', {}).get('intent', 'unknown')
                logger.info(f"Orchestrator determined intent: {intent}")
                
                # Handle course search results
                if 'course_search' in orchestrator_result:
                    course_result = orchestrator_result['course_search']
                    
                    # Handle multiple topics case
                    if course_result.get('multiple_topics', []):
                        topics = course_result.get('multiple_topics', [])
                        topics_formatted = ", ".join(topics)
                        
                        response_text = f"Based on our conversation, I see several topics we've discussed: {topics_formatted}. Which one would you like to find courses for?"
                        
                        # Save the assistant's message
                        assistant_message = Message.objects.create(
                            chat=chat,
                            role='assistant',
                            content=response_text
                        )
                        
                        # Store topics in chat metadata
                        metadata = {}
                        if hasattr(chat, 'metadata') and chat.metadata:
                            try:
                                metadata = json.loads(chat.metadata) if isinstance(chat.metadata, str) else chat.metadata
                                if not isinstance(metadata, dict):
                                    metadata = {}
                            except json.JSONDecodeError:
                                metadata = {}
                        
                        metadata['awaiting_topic_selection'] = True
                        metadata['topics'] = topics
                        chat.metadata = json.dumps(metadata)
                        chat.save()
                        
                        # Return response with topics
                        response_data = {
                            'chat_id': chat.id,
                            'response': response_text,
                            'topics': topics
                        }
                        logger.info(f"Returning response with multiple topics: {topics}")
                        return Response(response_data, status=status.HTTP_200_OK)
                    
                    # Handle regular course results
                    elif course_result.get('found', False) and course_result.get('courses', []):
                        courses = course_result.get('courses', [])
                        topic = course_result.get('topic', '')
                        logger.info(f"Found {len(courses)} courses for topic: {topic}")
                        
                        # Clear awaiting selection state
                        if awaiting_selection:
                            try:
                                metadata = json.loads(chat.metadata) if isinstance(chat.metadata, str) else chat.metadata
                                if isinstance(metadata, dict):
                                    metadata['awaiting_topic_selection'] = False
                                    chat.metadata = json.dumps(metadata)
                                    chat.save()
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to parse chat metadata JSON: {chat.metadata}")
                        
                        # Generate a response message
                        response_text = f"Based on your interest in {topic}, here are some recommended courses that might help you:"
                        
                        # Save the assistant's message
                        assistant_message = Message.objects.create(
                            chat=chat,
                            role='assistant',
                            content=response_text
                        )
                        
                        # Return the response with courses
                        response_data = {
                            'chat_id': chat.id,
                            'response': response_text,
                            'courses': courses
                        }
                        logger.info(f"Returning response with {len(courses)} courses")
                        return Response(response_data, status=status.HTTP_200_OK)
                    
                    # Handle need for clarification
                    elif course_result.get('needs_clarification', False):
                        response_text = "I'd be happy to find courses for you. Could you please specify what topic or skill you're interested in learning about?"
                        
                        # Save the assistant's message
                        assistant_message = Message.objects.create(
                            chat=chat,
                            role='assistant',
                            content=response_text
                        )
                        
                        # Return the clarification request
                        response_data = {
                            'chat_id': chat.id,
                            'response': response_text,
                            'needs_clarification': True
                        }
                        logger.info("Returning clarification request for course topic")
                        return Response(response_data, status=status.HTTP_200_OK)
                
                # Handle learning path results
                if 'learning_path' in orchestrator_result:
                    # Process learning path results and return
                    path_result = orchestrator_result['learning_path']
                    # Return appropriate response for learning path
                    # ... implementation for learning path
                    
                # Handle knowledge base results
                if 'knowledge_base' in orchestrator_result:
                    kb_result = orchestrator_result['knowledge_base']
                    response_text = kb_result.get('response', '')
                    
                    # Save the assistant's message
                    assistant_message = Message.objects.create(
                        chat=chat,
                        role='assistant',
                        content=response_text
                    )
                    
                    # Return the response
                    response_data = {
                        'chat_id': chat.id,
                        'response': response_text
                    }
                    return Response(response_data, status=status.HTTP_200_OK)
                
                # If no specific handler matched, use the general response
                response_text = orchestrator_result.get('response', '')
                if not response_text:
                    # Fall back to query_ollama if orchestrator didn't provide a response
                    response_text = query_ollama(prompt, chat_id=str(chat.id))
                else:
                    # Save the message if it wasn't already saved
                    assistant_message = Message.objects.create(
                        chat=chat,
                        role='assistant',
                        content=response_text
                    )
                
                # Return the response
                response_data = {
                    'chat_id': chat.id,
                    'response': response_text
                }
                return Response(response_data, status=status.HTTP_200_OK)
                    
            except Exception as e:
                logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
                return Response(
                    {"error": f"Failed to process chat request: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        else:
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


class CourseView(generics.ListCreateAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [AllowAny]

class CourseSearchView(generics.ListCreateAPIView):
    queryset = CourseSearch.objects.all()
    serializer_class = CourseSearchSerializer
    permission_classes = [AllowAny]

class LearningPathwayView(generics.ListCreateAPIView):
    queryset = LearningPathway.objects.all()
    serializer_class = LearningPathwaySerializer
    permission_classes = [AllowAny]

class KnowledgeSourceView(generics.ListCreateAPIView):
    queryset = KnowledgeSource.objects.all()
    serializer_class = KnowledgeSourceSerializer
    permission_classes = [AllowAny]

class KnowledgeChunkView(generics.ListCreateAPIView):
    queryset = KnowledgeChunk.objects.all()
    serializer_class = KnowledgeChunkSerializer
    permission_classes = [AllowAny]