'use client';

import { Modal } from './Modal';
import { KEYBOARD_SHORTCUTS } from '@/hooks/useKeyboardShortcuts';

interface KeyboardShortcutsHelpProps {
  isOpen: boolean;
  onClose: () => void;
}

export function KeyboardShortcutsHelp({ isOpen, onClose }: KeyboardShortcutsHelpProps) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Keyboard Shortcuts" size="md">
      <div className="space-y-3">
        {KEYBOARD_SHORTCUTS.map((shortcut, index) => (
          <div 
            key={index}
            className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700 last:border-0"
          >
            <span className="text-gray-700 dark:text-gray-300">{shortcut.description}</span>
            <div className="flex items-center gap-1">
              {shortcut.keys.map((key, keyIndex) => (
                <span key={keyIndex}>
                  <kbd className="px-2 py-1 text-xs font-semibold text-gray-800 bg-gray-100 border border-gray-300 rounded-lg dark:bg-gray-700 dark:text-gray-200 dark:border-gray-600">
                    {key}
                  </kbd>
                  {keyIndex < shortcut.keys.length - 1 && (
                    <span className="mx-1 text-gray-400">+</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-6 p-3 bg-indigo-50 dark:bg-indigo-900/30 rounded-lg">
        <p className="text-sm text-indigo-700 dark:text-indigo-300">
          💡 Press <kbd className="px-1.5 py-0.5 text-xs bg-white dark:bg-gray-800 rounded border">?</kbd> anytime to show this help
        </p>
      </div>
    </Modal>
  );
}
