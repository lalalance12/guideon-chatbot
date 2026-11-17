import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agno.agent import Agent
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TransactionTestCase
from rest_framework.test import APIClient

from .agents.course_search_agent import CourseSearchAgent
from .agents.flow_manager_agent import FlowManagerAgent
from .agents.intent_classifier_agent import IntentClassifierAgent
from .flows.intent_flows import FlowController
from .models import Chat, CourseSearch, Message
from .utils.intent_classifier import QueryIntent, extract_role_from_query


class ChatAccessTests(TransactionTestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="test-only")
        self.bob = User.objects.create_user(username="bob", password="test-only")
        self.chat = Chat.objects.create(user=self.alice, title="Alice's conversation")
        Message.objects.create(chat=self.chat, role="user", content="Alice's private message")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)

    def test_anonymous_history_requires_authentication(self):
        response = APIClient().get("/api/chats/")
        self.assertEqual(response.status_code, 401)

    def test_history_list_contains_only_owned_conversations(self):
        Chat.objects.create(user=self.bob)
        response = self.client.get("/api/chats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [str(self.chat.id)])

    def test_uuid_history_detail_is_available_only_to_owner(self):
        response = self.client.get(f"/api/chats/{self.chat.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["messages"][0]["content"], "Alice's private message")
        self.client.force_authenticate(self.bob)
        self.assertEqual(self.client.get(f"/api/chats/{self.chat.id}/").status_code, 404)

    def test_another_user_cannot_append_to_a_chat(self):
        self.client.force_authenticate(self.bob)
        with patch("api.views.query_ollama", return_value={"response": "Unexpected service execution"}) as service:
            response = self.client.post(
                "/api/chat/", {"prompt": "intruder", "chat_id": str(self.chat.id)}, format="json"
            )
        self.assertEqual(response.status_code, 404)
        service.assert_not_called()
        self.assertEqual(list(self.chat.messages.values_list("content", flat=True)), ["Alice's private message"])

    def test_nonexistent_explicit_chat_is_not_silently_replaced(self):
        with patch("api.views.query_ollama", return_value={"response": "Unexpected service execution"}) as service:
            response = self.client.post(
                "/api/chat/", {"prompt": "hello", "chat_id": str(uuid4())}, format="json"
            )
        self.assertEqual(response.status_code, 404)
        service.assert_not_called()
        self.assertEqual(Chat.objects.count(), 1)

    def test_owner_can_create_and_continue_chat_with_real_service(self):
        async def model_response(agent, *args, **kwargs):
            if agent.name == "IntentClassifier":
                return SimpleNamespace(content=json.dumps({
                    "intent": "general_conversation", "confidence": 0.95,
                    "needs_context": False, "entities": {},
                }))
            return SimpleNamespace(content="Hello from Guideon.")

        with (
            patch.object(Agent, "arun", model_response),
            patch("requests.sessions.Session.request", side_effect=AssertionError("Unexpected network call")),
            patch("httpx.Client.send", side_effect=AssertionError("Unexpected network call")),
            patch("httpx.AsyncClient.send", side_effect=AssertionError("Unexpected network call")),
        ):
            first = self.client.post("/api/chat/", {"prompt": "hello"}, format="json")
            self.assertEqual(first.status_code, 200)
            chat_id = str(first.data["chat_id"])
            second = self.client.post(
                "/api/chat/", {"prompt": "hello again", "chat_id": chat_id}, format="json"
            )
        self.assertEqual(second.status_code, 200)
        chat = Chat.objects.get(pk=chat_id, user=self.alice)
        self.assertEqual(list(chat.messages.filter(role="user").values_list("content", flat=True)), ["hello", "hello again"])
        self.assertEqual(chat.messages.filter(role="assistant").count(), 2)


class RegistrationTests(TransactionTestCase):
    def test_invalid_registration_is_a_client_error_without_password_logs(self):
        sentinel = "SYNTHETIC_PASSWORD_SENTINEL"
        with self.assertLogs("api.views", level="INFO") as captured:
            response = APIClient().post("/api/auth/register/", {
                "email": "not-an-email", "password": sentinel, "fullName": "Test User",
            }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(sentinel, "\n".join(captured.output))
        self.assertEqual(User.objects.count(), 0)

    def test_valid_registration_and_login_still_work(self):
        client = APIClient()
        credentials = {"email": "new-user@example.invalid", "password": "Test-only-strong-password!42"}
        response = client.post("/api/auth/register/", {**credentials, "fullName": "Test User"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["token"])
        self.assertEqual(client.post("/api/auth/login/", credentials, format="json").status_code, 200)


class ContextTests(TransactionTestCase):
    def test_real_vector_search_fallback_can_be_serialized(self):
        with patch("api.utils.query_vectors.generate_embedding", return_value=None):
            response = APIClient().post("/api/retrieve-context/", {"query": "skills for data analyst"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], len(response.data["context"]))
        self.assertTrue(response.data["context"][0]["text"])

    def test_search_envelope_accepts_actual_integer_chunk_ids(self):
        item = {"id": 42, "text": "Data analysis", "metadata": {"type": "skill"}, "distance": 0.1}
        with patch("api.views.search_similar_content", return_value={"found": True, "items": [item], "count": 1}):
            response = APIClient().post("/api/retrieve-context/", {"query": "data analysis"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["context"][0]["id"], 42)
        self.assertEqual(response.data["count"], 1)


class CourseEndpointTests(TransactionTestCase):
    def test_get_search_works_for_anonymous_and_authenticated_users(self):
        result = {"found": True, "courses": [{
            "title": "Python Basics", "provider": "Example", "url": "https://example.invalid/python",
            "description": "Learn Python", "rating": 4.5, "price": "Free",
        }]}
        client = APIClient()
        with patch.object(CourseSearchAgent, "process", new_callable=AsyncMock, return_value=result):
            anonymous = client.get("/api/course-search/", {"q": "Python"})
            self.assertEqual(anonymous.status_code, 200)
            self.assertEqual(CourseSearch.objects.count(), 0)
            user = User.objects.create_user(username="course-owner")
            client.force_authenticate(user)
            authenticated = client.get("/api/course-search/", {"q": "Python"})
        self.assertEqual(authenticated.status_code, 200)
        self.assertEqual(authenticated.data["courses"][0]["title"], "Python Basics")
        self.assertEqual(CourseSearch.objects.get().user, user)


class FlowTests(SimpleTestCase):
    def test_specific_role_names_preserve_seniority(self):
        for role in ("senior data scientist", "chief data scientist", "associate data analyst", "senior business intelligence analyst", "data scientist"):
            with self.subTest(role=role):
                self.assertEqual(extract_role_from_query(f"I want to become a {role}"), role)

    def test_course_clarification_reaches_course_agent(self):
        async def scenario():
            chat_id = str(uuid4())
            manager = FlowManagerAgent()
            try:
                await manager.process("Can you recommend some courses?", {"chat_id": chat_id, "intent": QueryIntent.COURSE_SEARCH})
                classifier = IntentClassifierAgent()
                model_json = json.dumps({"intent": "knowledge_base_query", "confidence": 0.9, "needs_context": False, "entities": {}})
                with patch.object(Agent, "arun", new_callable=AsyncMock, return_value=SimpleNamespace(content=model_json)):
                    result = await classifier.process("Python", {"chat_id": chat_id})
                routing = await manager.process("Python", {"chat_id": chat_id, **result})
                self.assertEqual(result["intent"], QueryIntent.COURSE_SEARCH)
                self.assertEqual(routing["flow_instructions"]["activate_agents"], ["course_agent"])
            finally:
                manager.reset_flow(chat_id)
        asyncio.run(scenario())

    def test_new_course_topic_replaces_prior_focus(self):
        controller = FlowController()
        for topic in ("Python", "SQL", "Statistics", "Machine Learning"):
            instructions = controller.process_query(f"Find courses on {topic}", QueryIntent.COURSE_SEARCH, {
                "extracted_entities": {"skill": topic},
            })
            self.assertEqual(controller.active_flow.context["search_topic"], topic)
            self.assertEqual(instructions["topic"], topic)

    def test_role_clarification_preserves_seniority(self):
        controller = FlowController()
        controller.process_query("I want a career", QueryIntent.LEARNING_PATHWAY, {})
        controller.process_query("senior data scientist", QueryIntent.LEARNING_PATHWAY, {
            "extracted_entities": {"extracted_role": "senior data scientist"},
        })
        self.assertEqual(controller.active_flow.context["current_entity"], "senior data scientist")


class CourseScrapingTests(SimpleTestCase):
    def test_optional_price_icon_does_not_discard_relevant_courses(self):
        search_html = '<a class="color-charcoal course-name" href="/course/python-1">Python</a>'
        course_html = '<h1 class="head-2 medium-up-head-1 small-down-margin-bottom-xsmall">Python Basics</h1><div class="wysiwyg text-1 line-wide">Programming fundamentals</div>'

        def http_get(url, **kwargs):
            return SimpleNamespace(text=search_html if "/search?" in url else course_html, raise_for_status=lambda: None)

        embedding = SimpleNamespace(json=lambda: {"embedding": [1.0, 0.0]}, raise_for_status=lambda: None)
        agent = CourseSearchAgent()
        with patch("requests.get", side_effect=http_get), patch("requests.post", return_value=embedding), patch("time.sleep"):
            result = asyncio.run(agent.process("Find courses on Python", {"focus_topic": "Python"}))
        self.assertTrue(result.get("found"), result)
        self.assertEqual(result["courses"][0]["title"], "Python Basics")
        self.assertIsInstance(result["courses"][0]["price"], str)
