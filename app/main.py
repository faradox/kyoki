import asyncio
import logging
import os
import random
import secrets
import string
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Set

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
WEBSOCKET_IDLE_TIMEOUT = float(os.getenv("WEBSOCKET_IDLE_TIMEOUT", "90"))

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("kyoki")

class CardType(str, Enum):
    EMPRESS = "EMPRESS"
    SAMURAI = "SAMURAI"
    NINJA = "NINJA"

class GameState(str, Enum):
    WAITING = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED = "FINISHED"

@dataclass
class Player:
    ws: WebSocket
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Anonymous Player"
    game_id: Optional[str] = None
    cards: list[CardType] = field(default_factory=list)
    current_play: Optional[dict[str, int | CardType]] = None
    wants_rematch: bool = False

    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.id == other.id

@dataclass
class Game:
    id: str
    player1: Player
    player2: Player
    state: GameState = GameState.IN_PROGRESS
    current_round: int = 1
    cards_per_type: int = 2

    async def reset_for_rematch(self):
        self.state = GameState.IN_PROGRESS
        self.current_round = 1
        self.player1.current_play = None
        self.player2.current_play = None
        self.player1.wants_rematch = False
        self.player2.wants_rematch = False

        # Reset and shuffle cards
        for p in [self.player1, self.player2]:
            p.cards = build_deck(self.cards_per_type)
            random.shuffle(p.cards)

        # Notify players with opponent names preserved
        await self.player1.ws.send_json({
            "type": "GAME_START",
            "player_num": 1,
            "cards": self.player1.cards,
            "opponent_name": self.player2.name,
            "message": "Rematch started!"
        })
        await self.player2.ws.send_json({
            "type": "GAME_START",
            "player_num": 2,
            "cards": self.player2.cards,
            "opponent_name": self.player1.name,
            "message": "Rematch started!"
        })

    async def handle_rematch_vote(self, player: Player):
        player.wants_rematch = True
        other_player = self.player2 if player == self.player1 else self.player1

        # Notify other player about the vote
        await other_player.ws.send_json({
            "type": "REMATCH_VOTE",
            "message": "Opponent wants a rematch!"
        })

        # If both players want rematch, reset and start new game
        if self.player1.wants_rematch and self.player2.wants_rematch:
            await asyncio.sleep(1.5)  # Short delay before reset
            await self.reset_for_rematch()
        
    async def handle_rematch_decline(self, player: Player):
        other_player = self.player2 if player == self.player1 else self.player1
        
        # Notify both players about the decline
        for p in [player, other_player]:
            await p.ws.send_json({
                "type": "REMATCH_DECLINED",
                "message": "Rematch declined. Returning to menu..."
            })

    async def handle_round(self):
        # Ensure both players have made their moves
        if not (self.player1.current_play and self.player2.current_play):
            return

        p1_card = self.player1.current_play["card"]
        p2_card = self.player2.current_play["card"]
        p1_card_index = self.player1.current_play["index"]
        p2_card_index = self.player2.current_play["index"]

        # Determine round outcome
        result = self.resolve_battle(p1_card, p2_card)
        
        # Remove cards from players' hands based on battle result
        if result == "STALEMATE":
            message = "Stalemate! Both cards return to hands."
        elif result == "P1_WINS":
            if p2_card == CardType.EMPRESS:
                self.state = GameState.FINISHED
                message = "Player 1 wins the game!"
            else:
                self.player2.cards.pop(p2_card_index)
                message = "Player 1 wins the round! Player 2's card is eliminated."
        elif result == "P2_WINS":
            if p1_card == CardType.EMPRESS:
                self.state = GameState.FINISHED
                message = "Player 2 wins the game!"
            else:
                self.player1.cards.pop(p1_card_index)
                message = "Player 2 wins the round! Player 1's card is eliminated."

        # Send update to both players
        round_data = {
            "type": "ROUND_RESULT",
            "p1_card": p1_card,
            "p2_card": p2_card,
            "result": result,
            "message": message,
            "game_state": self.state,
            "p1_cards": self.player1.cards,
            "p2_cards": self.player2.cards
        }

        await self.player1.ws.send_json(round_data | {"your_cards": self.player1.cards})
        await self.player2.ws.send_json(round_data | {"your_cards": self.player2.cards})

        # Reset current plays
        self.player1.current_play = None
        self.player2.current_play = None
        self.current_round += 1

    def resolve_battle(self, card1: CardType, card2: CardType) -> str:
        # Same cards = stalemate
        if card1 == card2:
            return "STALEMATE"
            
        # Empress vs Samurai: Empress wins
        if card1 == CardType.EMPRESS and card2 == CardType.SAMURAI:
            return "P1_WINS"
        if card2 == CardType.EMPRESS and card1 == CardType.SAMURAI:
            return "P2_WINS"
            
        # Samurai vs Ninja: Ninja wins
        if card1 == CardType.SAMURAI and card2 == CardType.NINJA:
            return "P1_WINS"
        if card2 == CardType.SAMURAI and card1 == CardType.NINJA:
            return "P2_WINS"
            
        # Ninja vs Empress: Ninja wins
        if card1 == CardType.NINJA and card2 == CardType.EMPRESS:
            return "P1_WINS"
        if card2 == CardType.NINJA and card1 == CardType.EMPRESS:
            return "P2_WINS"
            
        return "STALEMATE"  # Fallback case

# Global state
waiting_players: Set[Player] = set()
active_games: Dict[str, Game] = {}
vs_battle_players: Dict[str, Player] = {}  # code -> player mapping


def build_deck(cards_per_type: int) -> list[CardType]:
    return (
        [CardType.EMPRESS]
        + [CardType.SAMURAI] * cards_per_type
        + [CardType.NINJA] * cards_per_type
    )


def generate_battle_code() -> str:
    """Generate a unique 6-letter battle code"""
    while True:
        # Generate 6 uppercase letters
        code = ''.join(secrets.choice(string.ascii_uppercase) for _ in range(6))
        if code not in vs_battle_players:
            return code

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}

@app.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Wait for initial name message
    data = await websocket.receive_json()
    player = Player(ws=websocket)
    
    if data["type"] == "SET_NAME":
        player.name = data["name"] or "Anonymous Player"
    
    try:
        # Add to waiting queue
        waiting_players.add(player)
        await websocket.send_json({"type": "STATUS", "message": "Waiting for opponent..."})
        
        # Check for match
        if len(waiting_players) >= 2:
            # Get two players
            player1 = waiting_players.pop()
            player2 = waiting_players.pop()
            
            # Create game
            game_id = str(uuid.uuid4())
            game = Game(id=game_id, player1=player1, player2=player2)
            
            # Setup initial game state
            for p in [player1, player2]:
                p.game_id = game_id
                p.cards = build_deck(game.cards_per_type)
                random.shuffle(p.cards)
                
            active_games[game_id] = game
            
            # Notify players
            await player1.ws.send_json({
                "type": "GAME_START",
                "player_num": 1,
                "opponent_name": player2.name,
                "cards": player1.cards
            })
            await player2.ws.send_json({
                "type": "GAME_START",
                "player_num": 2,
                "opponent_name": player1.name,
                "cards": player2.cards
            })
        
        # Main game loop
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=WEBSOCKET_IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "PING"})
                    continue
                except WebSocketDisconnect:
                    break
            
            if data["type"] == "PLAY_CARD" and player.game_id:
                game = active_games[player.game_id]
                player.current_play = {
                    "card": data["card"],
                    "index": data["index"]
                }
                
                other_player = game.player2 if player == game.player1 else game.player1
                await other_player.ws.send_json({
                    "type": "OPPONENT_PLAYED",
                    "message": "Opponent has played their card!"
                })
                
                await game.handle_round()

            elif data["type"] == "REMATCH_REQUEST" and player.game_id:
                game = active_games[player.game_id]
                await game.handle_rematch_vote(player)

            elif data["type"] == "REMATCH_DECLINE" and player.game_id:
                game = active_games[player.game_id]
                await game.handle_rematch_decline(player)
                
    except WebSocketDisconnect:
        if player in waiting_players:
            waiting_players.remove(player)
        if player.game_id and player.game_id in active_games:
            game = active_games[player.game_id]
            other_player = game.player1 if player == game.player2 else game.player2
            await other_player.ws.send_json({
                "type": "OPPONENT_DISCONNECTED"
            })
            del active_games[player.game_id]

@app.websocket("/ws/vs_battle")
async def vs_battle_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Wait for initial name message
    data = await websocket.receive_json()
    player = Player(ws=websocket)
    
    if data["type"] == "SET_NAME":
        player.name = data["name"] or "Anonymous Player"
    
    battle_code: Optional[str] = None
    try:
        # Generate unique battle code for this player
        battle_code = generate_battle_code()
        vs_battle_players[battle_code] = player
        
        # Send the code to the player
        await websocket.send_json({
            "type": "BATTLE_CODE",
            "code": battle_code
        })
        
        # Go through the VS Battle setup dialog
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=WEBSOCKET_IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "PING"})
                    continue
                except WebSocketDisconnect:
                    break
            
            if data["type"] == "JOIN_BATTLE":
                opponent_code = data["code"].upper()
                if opponent_code not in vs_battle_players:
                    await websocket.send_json({
                        "type": "ERROR",
                        "message": "Invalid battle code. Please check and try again."
                    })
                    continue
                
                opponent = vs_battle_players[opponent_code]
                if opponent == player:
                    await websocket.send_json({
                        "type": "ERROR",
                        "message": "Cannot join your own battle."
                    })
                    continue
                
                # Create game
                game_id = str(uuid.uuid4())
                game = Game(id=game_id, player1=player, player2=opponent)
                
                # Setup initial game state
                for p in [player, opponent]:
                    p.game_id = game_id
                    p.cards = build_deck(game.cards_per_type)
                    random.shuffle(p.cards)
                
                active_games[game_id] = game
                
                # Remove both players from vs battle queue
                del vs_battle_players[battle_code]
                opponent_codes = [k for k, v in vs_battle_players.items() if v == opponent]
                for code in opponent_codes:
                    del vs_battle_players[code]
                
                # Notify players
                await player.ws.send_json({
                    "type": "GAME_START",
                    "player_num": 1,
                    "opponent_name": opponent.name,
                    "cards": player.cards
                })
                await opponent.ws.send_json({
                    "type": "GAME_START",
                    "player_num": 2,
                    "opponent_name": player.name,
                    "cards": opponent.cards
                })

            elif data["type"] == "PLAY_CARD" and player.game_id:
                game = active_games[player.game_id]
                player.current_play = {
                    "card": data["card"],
                    "index": data["index"]
                }
                
                other_player = game.player2 if player == game.player1 else game.player1
                await other_player.ws.send_json({
                    "type": "OPPONENT_PLAYED",
                    "message": "Opponent has played their card!"
                })
                
                await game.handle_round()

            elif data["type"] == "REMATCH_REQUEST" and player.game_id:
                game = active_games[player.game_id]
                await game.handle_rematch_vote(player)

            elif data["type"] == "REMATCH_DECLINE" and player.game_id:
                game = active_games[player.game_id]
                await game.handle_rematch_decline(player)
            
                
    except WebSocketDisconnect:
        if battle_code and battle_code in vs_battle_players:
            del vs_battle_players[battle_code]