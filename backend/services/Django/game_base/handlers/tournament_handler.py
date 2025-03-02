import threading

from game_base.models import TournamentBaseModel
from django.contrib.auth import get_user_model # type: ignore
from .core_base_handler import SendFunc, CoreBaseHandler

Player = get_user_model()

class TournamentHandlerBase(CoreBaseHandler):
	class Meta:
		abstract = True

	_type: str		= 'Tournament'
	_subtype: str	= 'Unknown'
	_MIN_PLAYERS	= 3
	_MAX_PLAYERS	= 8

	def __init__(self, tournament_id: str):
		super().__init__(tournament_id)
		self._model: type[TournamentBaseModel] | None	= None
		self._id										= tournament_id
		self._required_players: int						= self._MIN_PLAYERS
		self._state										= {
			'pending_matches': [],
			'finished_matches': [],
			'current_match': None,
			'leaderboard': {},
			'is_ready_to_start': {}
		}

	def _serialize_state(self):
		serialized_state = super()._serialize_state()
		del serialized_state['is_ready_to_start']
		return serialized_state

	def join_tournament(self, player: Player, send_func: SendFunc) -> int | None: # type: ignore
		player_index = super()._join(player, send_func)
		if player_index is not None:
			self._state['is_ready_to_start'].update({player.__str__(): False})
		return player_index

	def leave_tournament(self, player: Player): # type: ignore
		super()._leave(player)
		with self._lock:
			if player.__str__() in self._state['is_ready_to_start']:
				del self._state['is_ready_to_start'][player.__str__()]

	def _start_tournament(self, player_index: int):
		tournament_thread = threading.Thread(target=self._start_matches)
		super()._start(player_index, tournament_thread.start)

	def __ready_to_start(self)-> bool:
		return (all(self._state['is_ready_to_start'].values())
			and len(self.players) == self._required_players)

	def mark_ready_and_start(self, player_index: int):
		if not self._allowed_to_start(player_index):
			return
		player_str = self._indexes[player_index].__str__()
		self._state['is_ready_to_start'][player_str] = True
		self._send_func({
			'ready': f'Player #{player_index} {player_str} is ready to start.',
			'players_ready': f'{self._state['is_ready_to_start']}'
		})
		if self.__ready_to_start():
			self._start_tournament(player_index)

	def set_tournament_size(self, size: int):
		with self._lock:
			if self._model.status != 'waiting':
				raise ValueError('Cannot change size after tournament has started.')
		if size < self._MIN_PLAYERS or size > self._MAX_PLAYERS:
			raise ValueError(f'Must be between ' +
					f'{self._MIN_PLAYERS} and {self._MAX_PLAYERS}.')
		self._required_players = size
		for index in self._indexes:
			if index >= size:
				self.leave_tournament(self._indexes[index])
				self._send_func({
					'kicked': f'Player #{index} removed from tournament.',
					'index': f'{index}'
				})

	def set_description(self, description: str):
		with self._lock:
			if self._model.status != 'waiting':
				raise ValueError('Cannot change description after tournament has started.')
		self._model.description = description
		self._model.save()

	def _set_matches(self):
		raise NotImplementedError

	def _start_matches(self):
		raise NotImplementedError