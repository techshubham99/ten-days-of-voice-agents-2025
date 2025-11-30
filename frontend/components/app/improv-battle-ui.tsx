// frontend/components/app/improv-battle-ui.tsx
'use client';

import { useState, useEffect, useRef } from 'react';
import { 
  useRoomContext,
  useConnectionState,
  useDataChannel,
  useLocalParticipant
} from '@livekit/components-react';
import { DataPacket_Kind } from 'livekit-client';

interface GameState {
  player_name: string;
  current_round: number;
  max_rounds: number;
  rounds: Array<{
    scenario: string;
    host_reaction: string;
  }>;
  phase: 'intro' | 'awaiting_improv' | 'reacting' | 'done';
  current_scenario?: string;
}

interface ImprovBattleUIProps {
  playerName: string;
  onBack: () => void;
}

export function ImprovBattleUI({ playerName, onBack }: ImprovBattleUIProps) {
  const [gameState, setGameState] = useState<GameState>({
    player_name: playerName,
    current_round: 0,
    max_rounds: 3,
    rounds: [],
    phase: 'intro'
  });
  const [isRecording, setIsRecording] = useState(false);
  const [connectionError, setConnectionError] = useState<string>('');
  const hasSentJoinMessage = useRef(false);

  const room = useRoomContext();
  const connectionState = useConnectionState();
  const { localParticipant } = useLocalParticipant();
  
  const { send } = useDataChannel(
    'improv-battle',
    (msg) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(msg.payload));
        console.log('Received message:', data);
        
        if (data.type === 'game_state_update') {
          setGameState(data.state);
        } else if (data.type === 'scenario_start') {
          setGameState(prev => ({
            ...prev,
            current_scenario: data.scenario,
            phase: 'awaiting_improv'
          }));
        } else if (data.type === 'host_reaction') {
          setGameState(prev => ({
            ...prev,
            phase: 'reacting',
            rounds: [...prev.rounds, {
              scenario: data.scenario,
              host_reaction: data.reaction
            }]
          }));
        } else if (data.type === 'game_completed') {
          setGameState(prev => ({
            ...prev,
            phase: 'done'
          }));
        }
      } catch (error) {
        console.error('Error parsing game message:', error);
      }
    }
  );

  useEffect(() => {
    if (connectionState === 'connected' && localParticipant && !hasSentJoinMessage.current) {
      try {
        const data = {
          type: 'player_join',
          player_name: playerName,
          timestamp: Date.now()
        };
        send?.(new TextEncoder().encode(JSON.stringify(data)), DataPacket_Kind.RELIABLE);
        hasSentJoinMessage.current = true;
        setConnectionError('');
      } catch (error) {
        console.error('Error sending join message:', error);
        setConnectionError('Failed to connect to game');
      }
    }
  }, [connectionState, localParticipant, playerName, send]);

  const safeSend = (data: any) => {
    if (!send) {
      setConnectionError('Not connected to game server');
      return;
    }
    
    try {
      send(new TextEncoder().encode(JSON.stringify(data)), DataPacket_Kind.RELIABLE);
      setConnectionError('');
    } catch (error) {
      console.error('Error sending message:', error);
      setConnectionError('Failed to send game action');
    }
  };

  const endScene = () => {
    setIsRecording(false);
    safeSend({
      type: 'end_scene',
      timestamp: Date.now()
    });
  };

  const endGame = () => {
    safeSend({
      type: 'end_game',
      timestamp: Date.now()
    });
    onBack();
  };

  const startImprov = () => {
    setIsRecording(true);
    safeSend({
      type: 'start_improv',
      timestamp: Date.now()
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900 text-white">
      {/* Header */}
      <div className="bg-black/50 border-b border-white/20 p-4">
        <div className="flex justify-between items-center">
          <div className="flex items-center space-x-4">
            <button
              onClick={onBack}
              className="text-gray-300 hover:text-white transition-colors"
            >
              ← Back
            </button>
            <div>
              <h1 className="text-2xl font-bold text-yellow-400">🎭 Improv Battle</h1>
              <p className="text-gray-300">Player: {gameState.player_name}</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-lg font-semibold">
              Round {gameState.current_round} / {gameState.max_rounds}
            </div>
            <div className="text-sm text-gray-300 capitalize">
              Phase: {gameState.phase}
            </div>
          </div>
        </div>
      </div>

      {/* Connection Error */}
      {connectionError && (
        <div className="bg-red-600 text-white p-3 text-center">
          ⚠️ {connectionError}
        </div>
      )}

      {/* Main Content */}
      <div className="container mx-auto p-6 max-w-4xl">
        {/* Current Scenario */}
        {gameState.current_scenario && (
          <div className="bg-yellow-500/20 border border-yellow-400 rounded-xl p-6 mb-6">
            <h2 className="text-xl font-bold text-yellow-400 mb-3">🎯 Current Scenario</h2>
            <p className="text-lg">{gameState.current_scenario}</p>
            {gameState.phase === 'awaiting_improv' && (
              <div className="mt-4 flex items-center space-x-4">
                <div className={`w-3 h-3 rounded-full ${isRecording ? 'bg-red-500 animate-pulse' : 'bg-gray-500'}`}></div>
                <span className="text-sm">
                  {isRecording ? 'Performing your improv...' : 'Ready for your performance'}
                </span>
                {!isRecording ? (
                  <button
                    onClick={startImprov}
                    disabled={connectionState !== 'connected'}
                    className="ml-auto bg-green-500 hover:bg-green-600 disabled:bg-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    🎤 Start Improv
                  </button>
                ) : (
                  <button
                    onClick={endScene}
                    disabled={connectionState !== 'connected'}
                    className="ml-auto bg-red-500 hover:bg-red-600 disabled:bg-gray-600 px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    🏁 End Scene
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* Game Status */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          {/* Round Progress */}
          <div className="bg-white/10 rounded-xl p-6">
            <h3 className="font-bold text-lg mb-3">📊 Game Progress</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Rounds Completed:</span>
                <span>{gameState.current_round} / {gameState.max_rounds}</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div 
                  className="bg-green-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${(gameState.current_round / gameState.max_rounds) * 100}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Current Phase */}
          <div className="bg-white/10 rounded-xl p-6">
            <h3 className="font-bold text-lg mb-3">🎮 Game Status</h3>
            <div className="space-y-2">
              <div className="flex justify-between">
                <span>Phase:</span>
                <span className="capitalize">{gameState.phase}</span>
              </div>
              <div className="flex justify-between">
                <span>Connection:</span>
                <span className={
                  connectionState === 'connected' ? 'text-green-400' : 
                  connectionState === 'connecting' ? 'text-yellow-400' : 'text-red-400'
                }>
                  {connectionState}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Previous Rounds */}
        {gameState.rounds.length > 0 && (
          <div className="bg-white/10 rounded-xl p-6 mb-6">
            <h3 className="font-bold text-lg mb-4">📝 Previous Rounds</h3>
            <div className="space-y-4">
              {gameState.rounds.map((round, index) => (
                <div key={index} className="border-l-4 border-yellow-400 pl-4 py-2">
                  <div className="font-semibold text-yellow-300 mb-1">
                    Round {index + 1}
                  </div>
                  <div className="text-sm text-gray-300 mb-2">
                    <strong>Scenario:</strong> {round.scenario}
                  </div>
                  <div className="text-sm">
                    <strong>Host Feedback:</strong> {round.host_reaction}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex justify-center space-x-4">
          <button
            onClick={endGame}
            className="bg-red-500 hover:bg-red-600 px-6 py-3 rounded-lg font-semibold transition-colors"
          >
            🏁 End Game
          </button>
        </div>

        {/* Instructions */}
        <div className="mt-8 bg-black/30 rounded-xl p-6">
          <h3 className="font-bold text-lg mb-3">🎯 How to Play</h3>
          <ul className="space-y-2 text-sm text-gray-300">
            <li>• Listen to the host's scenario</li>
            <li>• Click "Start Improv" and perform your scene</li>
            <li>• Click "End Scene" when finished</li>
            <li>• Receive host feedback after each round</li>
            <li>• Complete all 3 rounds to finish the game</li>
          </ul>
        </div>
      </div>

      {/* Connection Status */}
      <div className={`fixed bottom-0 left-0 right-0 p-2 text-center text-sm ${
        connectionState === 'connected' ? 'bg-green-600' : 
        connectionState === 'connecting' ? 'bg-yellow-600' : 'bg-red-600'
      }`}>
        {connectionState === 'connected' ? '✅ Connected to Improv Battle' : 
         connectionState === 'connecting' ? '🔄 Connecting...' : '❌ Disconnected'}
      </div>
    </div>
  );
}