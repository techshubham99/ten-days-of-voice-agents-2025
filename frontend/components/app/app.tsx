// frontend/components/app/app.tsx
'use client';

import { useState } from 'react';
import { RoomAudioRenderer, StartAudio } from '@livekit/components-react';
import type { AppConfig } from '@/app-config';
import { SessionProvider } from '@/components/app/session-provider';
import { ViewController } from '@/components/app/view-controller';
import { Toaster } from '@/components/livekit/toaster';
import { ImprovBattleLobby } from '@/components/app/improv-battle-lobby';

interface AppProps {
  appConfig: AppConfig;
}

export function App({ appConfig }: AppProps) {
  const [gameMode, setGameMode] = useState<'default' | 'improv-battle'>('default');

  if (gameMode === 'improv-battle') {
    return (
      <SessionProvider appConfig={appConfig}>
        <ImprovBattleLobby onBack={() => setGameMode('default')} />
        <StartAudio label="Start Audio" />
        <RoomAudioRenderer />
        <Toaster />
      </SessionProvider>
    );
  }

  return (
    <SessionProvider appConfig={appConfig}>
      <div className="min-h-screen bg-gradient-to-br from-purple-900 via-blue-900 to-indigo-900">
        {/* Game Mode Selection */}
        <div className="fixed top-4 left-4 z-10">
          <button
            onClick={() => setGameMode('improv-battle')}
            className="bg-yellow-500 hover:bg-yellow-600 text-black font-bold py-2 px-4 rounded-lg transition-colors"
          >
            🎭 Start Improv Battle
          </button>
        </div>
        
        <main className="grid h-svh grid-cols-1 place-content-center">
          <ViewController />
        </main>
      </div>
      <StartAudio label="Start Improv Battle" />
      <RoomAudioRenderer />
      <Toaster />
    </SessionProvider>
  );
}