
import os
import pprint
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from openai import OpenAI
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from promptify_app.models import Chat, ChatMessage
from promptify_app.serializers import ChatMessageSerializer
from promptify_app.serializers import ChatSerializer

client = OpenAI(
    api_key=os.getenv("GEMINI_API_KEY"),
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

MODEL = "gemini-3.5-flash-lite"
SYSTEM_PROMPT = "You are a helpful assistant."

def createChatTitle(user_message):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Give a short, descriptive title for this conversation in not more than 5 words.",
                },
                {"role": "user", "content": user_message},
            ],
        )
        title = response.choices[0].message.content.strip()
    except Exception:
        title = user_message[:50]
    return title


@api_view(["POST"])
def prompt_gpt(request):
    chat_id = request.data.get("chat_id")
    content = request.data.get("content")

    if not chat_id:
        return Response({"error": "Chat ID was not provided."}, status=400)

    if not content:
        return Response({"error": "There was no prompt passed."}, status=400)

    chat, created = Chat.objects.get_or_create(id=chat_id)

    # Create the title only for a new chat (or one without a title)
    if created or not chat.title:
        chat.title = createChatTitle(content)
        chat.save()

    ChatMessage.objects.create(role="user", chat=chat, content=content)

    # Take the latest 10 messages, then put them back in chronological order
    recent_messages = chat.messages.order_by("-created_at")[:10]
    chat_messages = reversed(list(recent_messages))

    openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    openai_messages += [
        {"role": message.role, "content": message.content}
        for message in chat_messages
    ]

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=openai_messages,
        )
        # pprint.pprint(response)
        openai_reply = response.choices[0].message.content
    except Exception as error:
        print("GEMINI ERROR:", error)
        return Response({"error": f"An error from Openai: {str(error)}"}, status=500)

    ChatMessage.objects.create(role="assistant", content=openai_reply, chat=chat)
    return Response({"reply": openai_reply}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
def get_chat_messages(request, pk):
    chat = get_object_or_404(Chat, id=pk)
    chatmessages = chat.messages.order_by("created_at")
    serializer = ChatMessageSerializer(chatmessages, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def todays_chat(request):
    today = timezone.localdate()
    chats = Chat.objects.filter(created_at__date=today).order_by("-created_at")[:10]
    serializer = ChatSerializer(chats, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def yesterdays_chat(request):
    yesterday = timezone.localdate() - timedelta(days=1)
    chats = Chat.objects.filter(created_at__date=yesterday).order_by("-created_at")[:10]
    serializer = ChatSerializer(chats, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def seven_days_chat(request):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    seven_days_ago = today - timedelta(days=7)
    chats = Chat.objects.filter(
        created_at__date__lt=yesterday,
        created_at__date__gte=seven_days_ago,
    ).order_by("-created_at")[:10]
    serializer = ChatSerializer(chats, many=True)
    return Response(serializer.data)