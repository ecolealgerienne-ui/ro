'use client';

import { use, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { PreviewPanel } from '@/components/conversation/preview-panel';
import {
  findScenario,
  SUGGESTIONS,
  type ScriptedAction,
  type ScriptedPreview,
} from '@/components/conversation/scenarios';
import { ValidationCard } from '@/components/conversation/validation-card';
import { cn } from '@/lib/utils';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  time: string;
  pendingAction?: ScriptedAction;
}

export default function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: _workshopId } = use(params);
  const searchParams = useSearchParams();
  const prefill = searchParams?.get('q') ?? '';
  const [input, setInput] = useState(prefill);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'sys-welcome',
      role: 'assistant',
      content:
        'Bonjour. Je peux t\'aider à modifier le planning : changer une priorité client, décaler un OF, geler une opération, ou répondre à une question. Tape ta demande en langage naturel.',
      time: nowHHmm(),
    },
  ]);
  const [activePreview, setActivePreview] = useState<ScriptedPreview | null>(null);
  const [appliedIds, setAppliedIds] = useState<Set<string>>(new Set());
  const [cancelledIds, setCancelledIds] = useState<Set<string>>(new Set());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-submit si prefill via query param (lien depuis Gantt)
  useEffect(() => {
    if (prefill) {
      handleSubmit(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    const scenario = findScenario(trimmed);
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: trimmed,
      time: nowHHmm(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput('');

    // Tours de réponse séquentiels
    scenario.turns.forEach((turn, idx) => {
      setTimeout(
        () => {
          const isLast = idx === scenario.turns.length - 1;
          const assistantMsg: ChatMessage = {
            id: `a-${Date.now()}-${idx}`,
            role: 'assistant',
            content: turn,
            time: nowHHmm(),
            pendingAction: isLast && scenario.action.kind !== 'noop' ? scenario.action : undefined,
          };
          setMessages((m) => [...m, assistantMsg]);
          if (isLast && scenario.action.kind !== 'noop') {
            setActivePreview(scenario.action.preview);
          }
        },
        500 + idx * 800,
      );
    });
  }

  function handleConfirm(action: ScriptedAction) {
    setAppliedIds((s) => new Set(s).add(action.id));
    setMessages((m) => [
      ...m,
      {
        id: `sys-${Date.now()}`,
        role: 'assistant',
        content: `✓ Modification "${action.description}" appliquée. Une nouvelle version a été créée et le solveur est en train de re-planifier.`,
        time: nowHHmm(),
      },
    ]);
  }

  function handleCancel(action: ScriptedAction) {
    setCancelledIds((s) => new Set(s).add(action.id));
    setMessages((m) => [
      ...m,
      {
        id: `sys-${Date.now()}`,
        role: 'assistant',
        content: `Annulé. Le planning reste inchangé.`,
        time: nowHHmm(),
      },
    ]);
    setActivePreview(null);
  }

  return (
    <div className="grid h-full grid-cols-[1fr_420px] overflow-hidden">
      {/* Chat zone */}
      <div className="flex flex-col bg-white">
        <header className="border-b border-slate-200 px-6 py-4">
          <div className="text-sm text-slate-500">Conversation #1 — démarrée à {nowHHmm()}</div>
          <h2 className="font-semibold text-slate-900">Demander une modification</h2>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-6">
          {messages.map((m) => (
            <div
              key={m.id}
              className={cn('flex gap-2', m.role === 'user' ? 'justify-end' : 'justify-start')}
            >
              {m.role === 'assistant' && (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-sm">
                  🤖
                </div>
              )}
              <div
                className={cn(
                  'flex max-w-[75%] flex-col gap-1',
                  m.role === 'user' ? 'items-end' : 'items-start',
                )}
              >
                <div
                  className={cn(
                    'whitespace-pre-line rounded-2xl px-4 py-3 text-sm',
                    m.role === 'user'
                      ? 'rounded-br-sm bg-indigo-600 text-white'
                      : 'rounded-bl-sm bg-slate-100 text-slate-900',
                  )}
                >
                  {m.content}
                </div>
                {m.pendingAction &&
                  !appliedIds.has(m.pendingAction.id) &&
                  !cancelledIds.has(m.pendingAction.id) && (
                    <ValidationCard
                      title={`Appliquer : ${m.pendingAction.description} ?`}
                      body="Toute modification est validée par toi avant d'être appliquée."
                      ofImpactes={m.pendingAction.preview.impacted.length}
                      onConfirm={() => handleConfirm(m.pendingAction!)}
                      onCancel={() => handleCancel(m.pendingAction!)}
                    />
                  )}
                <span className="px-1 text-[10px] text-slate-400">{m.time}</span>
              </div>
              {m.role === 'user' && (
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-semibold text-white">
                  CA
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="border-t border-slate-200 bg-slate-50 p-4">
          <div className="mb-2 text-xs text-slate-500">💡 Suggestions</div>
          <div className="mb-3 flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setInput(s)}
                className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs hover:border-indigo-400 hover:text-indigo-700"
              >
                {s}
              </button>
            ))}
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSubmit(input);
            }}
            className="flex items-end gap-2"
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Écris ta demande en langage naturel — ex : 'Priorité 1 sur Safran'…"
              rows={2}
              className="flex-1 resize-none rounded-lg border border-slate-300 px-4 py-3 text-sm focus:border-indigo-500 focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(input);
                }
              }}
            />
            <Button type="submit">Envoyer</Button>
          </form>
          <div className="mt-2 flex items-start gap-1 text-[11px] text-slate-500">
            <span>⚠</span>
            <span>
              Toute modification proposée par l&apos;assistant sera{' '}
              <strong>validée par toi</strong> avant d&apos;être appliquée.
            </span>
          </div>
        </div>
      </div>

      {/* Preview impact */}
      <aside className="overflow-y-auto border-l border-slate-200 bg-slate-50">
        <div className="border-b border-slate-200 bg-white p-5">
          <h3 className="font-semibold text-slate-900">Aperçu de l&apos;impact</h3>
          <p className="mt-1 text-xs text-slate-500">
            Diff métriques + OF impactés si tu valides la modification proposée.
          </p>
        </div>
        <PreviewPanel preview={activePreview} />
      </aside>
    </div>
  );
}

function nowHHmm(): string {
  const d = new Date();
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
}
