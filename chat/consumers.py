import json
import re
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import User
from .models import Message
from asgiref.sync import sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs'].get('room_name', None)

        # ✅ Check if the user is authenticated
        if not self.scope["user"].is_authenticated:
            await self.close()  # Close WebSocket if user is not logged in
            return

        user1 = self.scope['user'].username
        user2 = self.room_name

        # ✅ Ensure `user1` and `user2` are not None
        if not user1 or not user2:
            await self.close()
            return  # ✅ Stop execution if user is invalid

        # ✅ Sanitize usernames to prevent errors
        safe_user1 = re.sub(r'[^a-zA-Z0-9_.-]', '_', user1)
        safe_user2 = re.sub(r'[^a-zA-Z0-9_.-]', '_', user2)

        # ✅ Use `_` instead of `sorted()`
        self.room_group_name = f"chat_{safe_user1}_{safe_user2}"

        # ✅ Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        # ✅ Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Handles incoming WebSocket messages."""
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        sender = self.scope['user']
        receiver = await self.get_receiver_user(sender)

        if not receiver:
            return  # ✅ Prevent errors if receiver doesn't exist

        # ✅ Save message to database
        await self.save_message(sender, receiver, message)

        # ✅ Send message to WebSocket group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'sender': sender.username,
                'receiver': receiver.username,
                'message': message
            }
        )

    async def chat_message(self, event):
        """Handles messages sent to WebSocket."""
        message = event['message']
        sender = event['sender']
        receiver = event['receiver']

        # ✅ Send message to WebSocket
        await self.send(text_data=json.dumps({
            'sender': sender,
            'receiver': receiver,
            'message': message
        }))

    @sync_to_async
    def save_message(self, sender, receiver, message):
        """Save messages to the database."""
        Message.objects.create(sender=sender, receiver=receiver, content=message)

    @sync_to_async
    def get_receiver_user(self, sender):
        """Find the receiver user by excluding the sender."""
        try:
            return User.objects.exclude(username=sender.username).get(username=self.room_name)
        except User.DoesNotExist:
            return None  # ✅ Return None if the user doesn't exist
