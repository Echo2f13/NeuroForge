'use client';

import { useEffect, useCallback, useState } from 'react';

type KeyHandler = (event: KeyboardEvent) => void;

interface ShortcutConfig {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
  handler: KeyHandler;
  description?: string;
  enabled?: boolean;
}

interface UseKeyboardShortcutsOptions {
  enabled?: boolean;
  preventDefault?: boolean;
}

export function useKeyboardShortcuts(
  shortcuts: ShortcutConfig[],
  options: UseKeyboardShortcutsOptions = {}
) {
  const { enabled = true, preventDefault = true } = options;

  const handleKeyDown = useCallback((event: KeyboardEvent) => {
    if (!enabled) return;

    // Don't trigger shortcuts when typing in inputs
    const target = event.target as HTMLElement;
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
      // Allow Escape to work even in inputs
      if (event.key !== 'Escape') return;
    }

    for (const shortcut of shortcuts) {
      if (shortcut.enabled === false) continue;

      const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase();
      const ctrlMatch = shortcut.ctrl ? (event.ctrlKey || event.metaKey) : !event.ctrlKey && !event.metaKey;
      const shiftMatch = shortcut.shift ? event.shiftKey : !event.shiftKey;
      const altMatch = shortcut.alt ? event.altKey : !event.altKey;

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        if (preventDefault) {
          event.preventDefault();
        }
        shortcut.handler(event);
        break;
      }
    }
  }, [shortcuts, enabled, preventDefault]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

// Pre-defined shortcuts for the app
export function useAppShortcuts({
  onGenerateQuiz,
  onGenerateFlashcards,
  onGenerateNotes,
  onToggleTheme,
  onFocusSearch,
  onNavigateNext,
  onNavigatePrev,
  onSubmit,
  onCancel,
}: {
  onGenerateQuiz?: () => void;
  onGenerateFlashcards?: () => void;
  onGenerateNotes?: () => void;
  onToggleTheme?: () => void;
  onFocusSearch?: () => void;
  onNavigateNext?: () => void;
  onNavigatePrev?: () => void;
  onSubmit?: () => void;
  onCancel?: () => void;
}) {
  const shortcuts: ShortcutConfig[] = [
    // Generation shortcuts
    {
      key: 'q',
      ctrl: true,
      handler: () => onGenerateQuiz?.(),
      description: 'Generate quiz',
      enabled: !!onGenerateQuiz,
    },
    {
      key: 'f',
      ctrl: true,
      shift: true,
      handler: () => onGenerateFlashcards?.(),
      description: 'Generate flashcards',
      enabled: !!onGenerateFlashcards,
    },
    {
      key: 'n',
      ctrl: true,
      shift: true,
      handler: () => onGenerateNotes?.(),
      description: 'Generate notes',
      enabled: !!onGenerateNotes,
    },
    // UI shortcuts
    {
      key: 'd',
      ctrl: true,
      handler: () => onToggleTheme?.(),
      description: 'Toggle dark mode',
      enabled: !!onToggleTheme,
    },
    {
      key: 'k',
      ctrl: true,
      handler: () => onFocusSearch?.(),
      description: 'Focus search',
      enabled: !!onFocusSearch,
    },
    // Navigation
    {
      key: 'ArrowRight',
      handler: () => onNavigateNext?.(),
      description: 'Next item',
      enabled: !!onNavigateNext,
    },
    {
      key: 'ArrowLeft',
      handler: () => onNavigatePrev?.(),
      description: 'Previous item',
      enabled: !!onNavigatePrev,
    },
    {
      key: 'Enter',
      ctrl: true,
      handler: () => onSubmit?.(),
      description: 'Submit',
      enabled: !!onSubmit,
    },
    {
      key: 'Escape',
      handler: () => onCancel?.(),
      description: 'Cancel/Close',
      enabled: !!onCancel,
    },
  ];

  useKeyboardShortcuts(shortcuts);
}

// Keyboard shortcuts help modal content
export const KEYBOARD_SHORTCUTS = [
  { keys: ['1'], description: 'Documents tab' },
  { keys: ['2'], description: 'Quiz tab' },
  { keys: ['3'], description: 'Flashcards tab' },
  { keys: ['4'], description: 'Notes tab' },
  { keys: ['5'], description: 'AI Tutor tab' },
  { keys: ['6'], description: 'Mind Map tab' },
  { keys: ['Ctrl', 'B'], description: 'Toggle sidebar' },
  { keys: ['→'], description: 'Next question/card' },
  { keys: ['←'], description: 'Previous question/card' },
  { keys: ['Space'], description: 'Flip flashcard' },
  { keys: ['Esc'], description: 'Close modal/cancel' },
  { keys: ['?'], description: 'Show keyboard shortcuts' },
];

// Hook to show keyboard shortcuts help
export function useKeyboardShortcutsHelp() {
  const [isOpen, setIsOpen] = useState(false);

  useKeyboardShortcuts([
    {
      key: '?',
      shift: true,
      handler: () => setIsOpen(true),
      description: 'Show keyboard shortcuts',
    },
  ]);

  return {
    isOpen,
    open: () => setIsOpen(true),
    close: () => setIsOpen(false),
  };
}
