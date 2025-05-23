import json

from asgiref.sync import async_to_sync # type: ignore
from channels.generic.websocket import WebsocketConsumer # type: ignore
from channels.exceptions import StopConsumer # type: ignore
from django.contrib.auth import get_user_model # type: ignore
from game_base.managers.manager_base import ManagerBase
from game_base.handlers.core_base_handler import CoreBaseHandler
from typing import Any, Tuple

from player.middleware.jwt_cookie_auth import CookieJWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken # type: ignore

Player = get_user_model()

class CoreBaseConsumer(WebsocketConsumer):
	class Meta:
		abstract = True

	class __HandlerFunc():
		def __init__(self, outer):
			self.outer = outer

		def join(self, player, object_id):
			if self.outer._handler._type == 'Tournament':
				return self.outer._handler.join_tournament(player, object_id)
			else:
				return self.outer._handler.join_match(player, object_id)

		def leave(self, player):
			if self.outer._handler._type == 'Tournament':
				return self.outer._handler.leave_tournament(player)
			else:
				return self.outer._handler.leave_match(player)

		def start(self, player_index):
			if self.outer._handler._type == 'Tournament':
				return self.outer._handler.mark_ready_and_start(player_index)
			else:
				return self.outer._handler.start_game(player_index)

	_type		= 'Core'
	_subtype	= 'Abstract'

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._handler: type[CoreBaseHandler] | None	= None
		self._manager: type[ManagerBase] | None		= None
		self._id: str								= None
		self.player: Player							= None # type: ignore
		self.player_index: int						= None
		self._already_in: bool						= False
		self.__handler_func							= self.__HandlerFunc(self)

	def connect(self):
		super().connect()
		cookies = self.scope['cookies']
		if not 'access_token' in cookies:
			self.send(json.dumps({
				'type': 'error',
				'details': 'No access token provided, please login.'
			}))
			self.close()
			return
		access_token = cookies.get('access_token')
		try:
			authenticator = CookieJWTAuthentication()
			validated_token = authenticator.get_validated_token(access_token)
			self.player = authenticator.get_user(validated_token)
		except InvalidToken:
			self.send(json.dumps({
				'type': 'error',
				'details': 'Invalid token.'
			}))
			self.close()
			return
		except Exception as e:
			self.send(json.dumps({
				'type': 'error',
				'details': str(e)
			}))
			self.close()
			return
		self.send(json.dumps({
			'message': f'Connected to {self._subtype} {self._type} server.'
		}))

	def _send_to_group(self, message, player_index: int | None = -1) -> None:
		try:
			if player_index is None:
				self.send(text_data=json.dumps(message))
				return
			async_to_sync(self.channel_layer.group_send)(self._id, {
				'type': 'group.message',
				'message': message,
				'index': player_index,
			})
		except Exception as e:
			print("Error sending message to group:", e)
			raise StopConsumer()

	def group_message(self, event):
		message = event['message']
		index = event['index']
		if index == self.player_index or index == -1:
			self.send(text_data=json.dumps(message))

	def _set_handler(self, object_id, handler: type[CoreBaseHandler]):
		object_id += f'_{handler._type.lower()}_{self._subtype.lower()}'
		try:
			async_to_sync(self.channel_layer.group_add)(object_id, self.channel_name)
		except TypeError as e:
			self.send(json.dumps({'error': str(e)}))
			return
		self._id = object_id
		self._handler = self._manager._get_object(handler, object_id)

	def _join_lobby(self, object_id, handler: type[CoreBaseHandler]):
		self._set_handler(str(object_id), handler)
		if self._id is None:
			return
		self.player_index = self.__handler_func.join(self.player, self._send_to_group)
		if self.player_index is None:
			self.player = None
			self.send(json.dumps({
				'type': 'error',
				'details': f'Failed to join {self._subtype} {self._type} lobby.'
			}))
			async_to_sync(self.channel_layer.group_discard)(self._id, self.channel_name)
			return
		self._already_in = True

	def receive(self, text_data) -> Tuple[Any, Any] | None:
		text_data_json = json.loads(text_data)
		action = text_data_json.get('action')

		if action == 'join_lobby':
			if self._already_in:
				self.send(json.dumps({
					'type': 'error',
					'details': f'You are already in a {self._subtype} {self._type}.'
				}))
				return None, None
			object_id = text_data_json.get(f'{self._type.lower()}_id')
			try:
				if self.player == None:
					raise Player.DoesNotExist
			except Player.DoesNotExist:
				self.send(json.dumps({'message': 'Player not found.'}))
				return None, None
			self.join_lobby(object_id)
			return None, None

		elif action == f'start_{self._type.lower()}':
			if not self._handler:
				self.send(json.dumps({
					'type': 'error',
					'details': f'You are not in a {self._subtype} {self._type}.'
				}))
				return None, None
			try:
				self.__handler_func.start(self.player_index)
			except ValueError as e:
				self.send(json.dumps({
					'message': str(e)
				}))
			return None, None
		return [text_data_json, action]

	def disconnect(self, close_code):
		if self._handler:
			async_to_sync(self.channel_layer.group_discard)(self._id, self.channel_name)
			self.__handler_func.leave(self.player)
			if len(self._handler.players) == 0 and self._id:
				self._manager._remove_object(self._id)

	def join_lobby(self, object_id):
		raise NotImplementedError('You must implement this method in the child'
							+ f' class to specify the {self._type} handler.')
		return self._join_lobby(object_id, GameHandlerBase)