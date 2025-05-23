
import { updateElements } from "./draw_game.js";
import { keysPressed } from "./movement_game.js";
import { cleanupGame, resetGame } from "./game.js";
import { getCookie } from "../utils.js";
import { showToast, deactivateButton } from "../utils.js";
import {
	BOARD_HEIGHT,
	player1,
	player2,
	ball,
	setAnimationId,
	getAnimationId,
} from "./init_game.js";
import { changeLanguage } from "../translations.js";
import { removeErrorMessage, showErrorMessage } from "../error_handling.js";
import { showWinningScreen } from "../winning_screen.js";
import { refreshAccessToken } from "../authentication.js";

export {
	socket,
	startGame,
	joinGame,
	initSocket,
	resetSocket,
}

let	socket;

function startGame() {
	console.log('Starting game');
	const message = {
		action: 'start_game',
	};
	const messageJSON = JSON.stringify(message);
	sendToSocket(messageJSON);
	// onlineGameLoop();
}

//Main Loop
function onlineGameLoop() {
	const gameBoard = document.getElementById('gameBoard');
	if (!gameBoard) {
		console.log('Game board not found, stopping game loop');
		cleanupGame();
	}
	handleMovement();
	updateElements();
	setAnimationId(requestAnimationFrame(onlineGameLoop));
}

function handleMovement() {
	let direction;

	if (keysPressed['w'] || keysPressed['ArrowUp'])
		direction = 'up';
	if (keysPressed['s'] || keysPressed['ArrowDown'])
		direction = 'down';
	if (!direction)
		return ;
	const message = {
		action: 'move',
		move: direction,
	};
	const messageJSON = JSON.stringify(message);
	if (socket && socket.readyState === WebSocket.OPEN)
		socket.send(messageJSON);
};

let retries = 0;
function joinGame() {
	if (!socket || socket.readyState !== WebSocket.OPEN) {
		console.warn('Error: WebSocket connection is not open');
		if (retries < 10) {
			setTimeout(joinGame, 100);
			retries++;
		} else {
			console.error('Error: WebSocket connection failed to open');
			showToast('Error', 'WebSocket connection failed to open, please try again later');
		}
		return;
	}
	retries = 0;
	const player_pk = getCookie('user_id');
	const lobbyIdField = document.getElementById('lobbyId');
	const lobbyId = lobbyIdField.value;
	const lobbyContainer = document.getElementById('lobbyInput');

	removeErrorMessage(lobbyIdField);
	if (!lobbyId || lobbyId.trim() === '') {
		showErrorMessage(lobbyIdField, 'Invalid lobby ID');
		return;
	}
	const message = {
		action: 'join_lobby',
		game_id: lobbyId,
	};
	const messageJSON = JSON.stringify(message);
	sendToSocket(messageJSON);

	lobbyContainer.style.display = 'none';
}

function sendToSocket(message) {
	console.log("Sending message:", message);
	if (!socket) {
		console.warn('Warning: WebSocket connection is not established');
		return;
	}
	socket.send(message);
}

async function initSocket() {
	if (socket) {
		console.warn('Socket already exists');
		return;
	}
	await refreshAccessToken();
	socket = new WebSocket('/ws/pong/');
	socket.onopen = () => {
		console.log('WebSocket connection established');
	};
	socket.onmessage = (event) => {
		parseMessage(event.data);
	};
	socket.onerror = (error) => {
		console.error('WebSocket Error:', error);
	};
	socket.onclose = () => {
		console.log('WebSocket connection closed');
	};
}

function resetSocket() {
	if (socket && socket.readyState === WebSocket.OPEN) {
		socket.close();
	}
	socket = null;
}

function parseMessage(data) {
	let message;
	const gameTimer = document.getElementById('scoreGame');

	try {
		message = JSON.parse(data);
	} catch (error) {
		console.error('Error parsing message:', error);
		return;
	}
	if (message.type === 'pong_game_update') {
		updateGame(message.game_state);
		deactivateButton('startGame');
	} else if (message.type === 'game_over') {
		gameOver(message.game_state);
	} else if (message.type === 'lobby_update') {
		updateLobby(message.players);
	} else if (message.type === 'countdown' && message.message) {
		if (getAnimationId() === null)
			onlineGameLoop();
		deactivateButton('startGame');
		gameTimer.textContent = message.message[17] + ' : ' + message.message[17];
		console.log('Received message:', message.message);
	} else if (message.type === 'error') {
		console.log('Error:', message.details);
		showToast('Error', message.details);
	} else if (message.message)
		console.log('Received message:', message.message);
	else
		console.log('Received message:', message);
}

function updateGame(game_state) {
	const X = 0;
	const Y = 1;
	const scale = BOARD_HEIGHT / 500;

	if (getAnimationId() === null)
		setAnimationId(requestAnimationFrame(onlineGameLoop));
	player1.y = game_state.paddle_1_position * scale;
	player2.y = game_state.paddle_2_position * scale;
	ball.x = game_state.ball_position[X] * scale;
	ball.y = game_state.ball_position[Y] * scale;
	updateScore(game_state.score);
}

function updateScore(score) {
	const scoreContainer = document.getElementById('scoreGame');
	const player1Container = document.getElementById('player1Name');
	const player2Container = document.getElementById('player2Name');

	// Extract player names from the score object
	const players = Object.keys(score);
	const player1Name = players[0];
	const player2Name = players[1];

	// Extract scores
	const player1Score = score[player1Name];
	const player2Score = score[player2Name];

	// Update the frontend
	player1Container.textContent = player1Name.charAt(0).toUpperCase() + player1Name.slice(1);
	player2Container.textContent = player2Name.charAt(0).toUpperCase() + player2Name.slice(1);
	scoreContainer.textContent = `${player1Score} : ${player2Score}`;
}

function gameOver(game_state) {
	console.log('Game over:', game_state);
	resetSocket();
	resetGame();
	updateScore(game_state.score);
	showWinningScreen('winningScreen', game_state.score, 'play');
}

function updateLobby(players) {
	const player1Container = document.getElementById('player1Name');
	const player2Container = document.getElementById('player2Name');

	if (getAnimationId() !== null)
		return;
	player1Container.setAttribute('data-translate', 'waitingPlayer1');
	player2Container.setAttribute('data-translate', 'waitingPlayer2');
	for (const player of players) {
		if (player.index === 0) {
			player1Container.textContent = player.username.charAt(0).toUpperCase() + player.username.slice(1);
			player1Container.setAttribute('data-translate', '');
		} else if (player.index === 1) {
			player2Container.textContent = player.username.charAt(0).toUpperCase() + player.username.slice(1);
			player2Container.setAttribute('data-translate', '');
		}
	}
	changeLanguage();
}
