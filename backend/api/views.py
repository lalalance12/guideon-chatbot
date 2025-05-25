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
from .models import Chat, Message, Course, CourseSearch, LearningPathway, KnowledgeSource, KnowledgeChunk, UserLearnedCourse
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
    permission_classes = [AllowAny]

    def get(self, request):
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {"error": "Please provide a search query using the 'q' parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Create a context dict with education_advice intent
            context = {
                'intent': QueryIntent.EDUCATION_ADVICE,
                'confidence': 0.8
            }
            
            # Use our CourseSearchAgent
            agent = CourseSearchAgent()
            import asyncio
            result = asyncio.run(agent.process(query, context))
            
            if not result.get('found', False):
                return Response(
                    {"error": result.get('message', 'No courses found')},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Save matched courses to the database
            courses_data = []
            user = request.user
            chat_id = request.query_params.get('chat_id', None)
            chat = None
            
            if chat_id:
                try:
                    chat = Chat.objects.get(id=chat_id)
                except Chat.DoesNotExist:
                    pass
            
            for course_info in result.get('courses', []):
                # Check if course with the same URL already exists
                course, created = Course.objects.get_or_create(
                    url=course_info['url'],
                    defaults={
                        'title': course_info['title'],
                        'provider': course_info['provider'],
                        'description': course_info.get('description', ''),
                        'rating': course_info.get('rating', 0.0),
                        'metadata': {
                            'price': course_info.get('price', ''),
                            'similarity_score': course_info.get('similarity_score', 0.0),
                            'matched_skill': course_info.get('matched_skill', {})
                        }
                    }
                )
                
                # Record this search
                CourseSearch.objects.create(
                    query=query,
                    user=user,
                    course=course,
                    chat=chat
                )
                
                # Add to response data
                courses_data.append({
                    'title': course.title,
                    'provider': course.provider,
                    'rating': course.rating if course.rating is not None else 0.0,
                    'price': course_info.get('price', ''),
                    'description': course.description,
                    'url': course.url
                })
            
            # Return the courses found
            return Response(
                {"courses": courses_data},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error in course search: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to search for courses: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

class UserCourseTakeView(APIView):
    """
    API endpoint for users to add courses they want to take
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        course_id = request.data.get('course_id')
        if not course_id:
            return Response(
                {"error": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            course = Course.objects.get(id=course_id)
            
            # Create or update user-course relationship
            user_course, created = UserLearnedCourse.objects.get_or_create(
                user=request.user,
                course=course,
                defaults={
                    'status': 'in_progress'
                }
            )
            
            if not created:
                # If the relationship already existed, we just return it without changes
                pass
                
            return Response({
                'success': True,
                'message': 'Course added to your learning path',
                'user_course': {
                    'id': user_course.id,
                    'course_id': course.id,
                    'course_title': course.title,
                    'status': user_course.status,
                    'learned_at': user_course.learned_at
                }
            }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
            
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error taking course: {str(e)}", exc_info=True)
            return Response(
                {"error": f"Failed to take course: {str(e)}"},
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
                except Chat.DoesNotExist:
                    logger.warning(f"Chat ID {chat_id} not found, creating new chat")
                    chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
            else:
                logger.info("No chat_id provided, creating new chat")
                chat = Chat.objects.create(user=request.user if request.user.is_authenticated else None)
                
            logger.info(f"Using chat with ID: {chat.id}")
            
            try:
                # Process the message using our centralized service
                # Note: Messages are now saved inside the service
                result = query_ollama(prompt, chat_id=str(chat.id)) 
                
                # Check if we got course results
                if 'courses' in result:
                    # Return response with courses
                    response_data = {
                        'chat_id': chat.id,
                        'response': result['response'],
                        'courses': result['courses']
                    }
                    logger.info(f"Returning response with courses")
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    # Return standard text response
                    response_data = {
                        'chat_id': chat.id,
                        'response': result['response']
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

class TakeCourseView(APIView):
    """
    API endpoint for users to take a course and store course details.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Extract course details from request
        course_data = request.data.get('course')
        if not course_data:
            return Response({"error": "Course data is required."}, status=status.HTTP_400_BAD_REQUEST)

        url = course_data.get('url')
        if not url:
            return Response({"error": "Course URL is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if course exists, else create
        course, created = Course.objects.get_or_create(
            url=url,
            defaults={
                'title': course_data.get('title', ''),
                'provider': course_data.get('provider', ''),
                'description': course_data.get('description', ''),
                'rating': course_data.get('rating', None),
                'price': course_data.get('price', ''),
                'matching_skill': course_data.get('matching_skill', ''),
                'metadata': course_data.get('metadata', {})
            }
        )

        # Create CourseSearch entry
        CourseSearch.objects.create(
            query=course_data.get('query', ''),
            user=request.user,
            course=course,
            chat_id=course_data.get('chat_id', None)
        )

        # Create or update UserLearnedCourse
        user_course, _ = UserLearnedCourse.objects.get_or_create(
            user=request.user,
            course=course,
            defaults={
                'status': 'in_progress',
                'skill_text': course_data.get('matching_skill', '')
            }
        )

        return Response({
            'success': True,
            'course_id': course.id,
            'user_course_id': user_course.id,
            'course_title': course.title
        }, status=status.HTTP_201_CREATED)

class UserCoursesView(APIView):
    """
    API endpoint to get all courses the current user has enrolled in, with course details and status.
    Supports filtering by status (?status=ongoing|completed).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status')
        user_courses = UserLearnedCourse.objects.filter(user=request.user)
        if status_filter:
            user_courses = user_courses.filter(status=status_filter)
        # Prefetch related course details
        user_courses = user_courses.select_related('course')
        data = [
            {
                'id': uc.id,
                'status': uc.status,
                'learned_at': uc.learned_at,
                'skill_text': uc.skill_text,
                'course': {
                    'id': uc.course.id,
                    'title': uc.course.title,
                    'provider': uc.course.provider,
                    'url': uc.course.url,
                    'description': uc.course.description,
                    'rating': uc.course.rating,
                    'price': uc.course.price,
                    'matching_skill': uc.course.matching_skill,
                    'metadata': uc.course.metadata,
                }
            }
            for uc in user_courses
        ]
        return Response(data, status=status.HTTP_200_OK)

class CompleteCourseView(APIView):
    """
    API endpoint to mark a user's course as completed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_course_id = request.data.get('user_course_id')
        if not user_course_id:
            return Response({"error": "user_course_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user_course = UserLearnedCourse.objects.get(id=user_course_id, user=request.user)
            user_course.status = 'completed'
            user_course.save()
            return Response({"success": True, "message": "Course marked as completed."}, status=status.HTTP_200_OK)
        except UserLearnedCourse.DoesNotExist:
            return Response({"error": "User course not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error completing course: {str(e)}", exc_info=True)
            return Response({"error": f"Failed to complete course: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)