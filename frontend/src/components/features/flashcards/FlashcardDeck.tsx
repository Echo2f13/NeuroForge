'use client';

import { useState, useCallback, useEffect } from 'react';
import { Flashcard, Citation } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { CitationList } from '@/components/citations';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

interface FlashcardDeckProps {
  flashcards: Flashcard[];
  subjectId?: string;
  onComplete?: (scores: number[]) => void;
}

export function FlashcardDeck({ flashcards, subjectId, onComplete }: FlashcardDeckProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);
  const [scores, setScores] = useState<number[]>([]);
  const [showHint, setShowHint] = useState(false);

  const currentCard = flashcards[currentIndex];
  const isLastCard = currentIndex === flashcards.length - 1;
  const progress = ((currentIndex + 1) / flashcards.length) * 100;

  // Reset state when flashcards change
  useEffect(() => {
    setCurrentIndex(0);
    setIsFlipped(false);
    setScores([]);
    setShowHint(false);
  }, [flashcards]);

  const flipCard = useCallback(() => {
    setIsFlipped(prev => !prev);
    setShowHint(false);
  }, []);

  const nextCard = useCallback(() => {
    if (currentIndex < flashcards.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setIsFlipped(false);
      setShowHint(false);
    }
  }, [currentIndex, flashcards.length]);

  const prevCard = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1);
      setIsFlipped(false);
      setShowHint(false);
    }
  }, [currentIndex]);

  const rateCard = useCallback((score: number) => {
    setScores(prev => [...prev, score]);
    if (isLastCard) {
      onComplete?.([...scores, score]);
    } else {
      nextCard();
    }
  }, [isLastCard, scores, onComplete, nextCard]);

  // Keyboard shortcuts
  useKeyboardShortcuts([
    { key: ' ', handler: flipCard, description: 'Flip card' },
    { key: 'ArrowRight', handler: nextCard, description: 'Next card' },
    { key: 'ArrowLeft', handler: prevCard, description: 'Previous card' },
    { key: 'h', handler: () => setShowHint(true), description: 'Show hint' },
    { key: '1', handler: () => isFlipped && rateCard(1), description: 'Rate: Again' },
    { key: '2', handler: () => isFlipped && rateCard(3), description: 'Rate: Hard' },
    { key: '3', handler: () => isFlipped && rateCard(4), description: 'Rate: Good' },
    { key: '4', handler: () => isFlipped && rateCard(5), description: 'Rate: Easy' },
  ]);

  if (flashcards.length === 0) {
    return (
      <EmptyState
        icon={EmptyState.icons.flashcard}
        title="No flashcards yet"
        description="Generate flashcards for a topic to start studying"
      />
    );
  }

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between items-center mb-2">
          <span className="text-sm text-gray-600 dark:text-gray-400">
            Card {currentIndex + 1} of {flashcards.length}
          </span>
          <Badge variant={currentCard.difficulty === 'easy' ? 'success' : currentCard.difficulty === 'hard' ? 'error' : 'warning'}>
            {currentCard.difficulty}
          </Badge>
        </div>
        <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
          <div 
            className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Flashcard */}
      <div 
        className="perspective-1000 cursor-pointer mb-6"
        onClick={flipCard}
        role="button"
        aria-label={isFlipped ? 'Show question' : 'Show answer'}
        tabIndex={0}
        onKeyDown={(e) => e.key === 'Enter' && flipCard()}
      >
        <div 
          className={`
            relative w-full min-h-[300px] transform-style-3d transition-transform duration-500
            ${isFlipped ? 'rotate-y-180' : ''}
          `}
        >
          {/* Front (Question) */}
          <Card 
            className="absolute inset-0 backface-hidden flex flex-col items-center justify-center p-8 text-center"
            padding="none"
          >
            <div className="text-4xl mb-4">❓</div>
            <p className="text-xl font-medium text-gray-900 dark:text-white leading-relaxed">
              {currentCard.question}
            </p>
            
            {/* Hint */}
            {currentCard.hint && (
              <div className="mt-6">
                {showHint ? (
                  <p className="text-sm text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/30 px-4 py-2 rounded-lg">
                    💡 {currentCard.hint}
                  </p>
                ) : (
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowHint(true); }}
                    className="text-sm text-gray-500 hover:text-indigo-600 dark:hover:text-indigo-400"
                  >
                    Need a hint? Press H
                  </button>
                )}
              </div>
            )}
            
            <p className="mt-6 text-sm text-gray-400">
              Click or press Space to reveal answer
            </p>
          </Card>

          {/* Back (Answer) */}
          <Card 
            className="absolute inset-0 backface-hidden rotate-y-180 flex flex-col items-center justify-center p-8 text-center bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-950/50 dark:to-purple-950/50"
            padding="none"
          >
            <div className="text-4xl mb-4">✨</div>
            <p className="text-xl font-medium text-gray-900 dark:text-white leading-relaxed">
              {currentCard.answer}
            </p>
            
            {/* Mnemonic */}
            {currentCard.mnemonic && (
              <div className="mt-4 p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                <p className="text-sm text-yellow-800 dark:text-yellow-200">
                  🧠 <strong>Remember:</strong> {currentCard.mnemonic}
                </p>
              </div>
            )}

            {/* Related topics */}
            {currentCard.related_topics && currentCard.related_topics.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2 justify-center">
                {currentCard.related_topics.map((topic, i) => (
                  <Badge key={i} variant="info" size="sm">{topic}</Badge>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>

      {/* Rating buttons (shown when flipped) */}
      {isFlipped && (
        <div className="mb-6 animate-fade-in">
          <p className="text-center text-sm text-gray-600 dark:text-gray-400 mb-3">
            How well did you know this?
          </p>
          <div className="flex justify-center gap-2">
            <Button variant="danger" size="sm" onClick={() => rateCard(1)}>
              😫 Again
            </Button>
            <Button variant="secondary" size="sm" onClick={() => rateCard(3)}>
              😕 Hard
            </Button>
            <Button variant="secondary" size="sm" onClick={() => rateCard(4)}>
              🙂 Good
            </Button>
            <Button variant="success" size="sm" onClick={() => rateCard(5)}>
              😄 Easy
            </Button>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <Button
          variant="ghost"
          onClick={prevCard}
          disabled={currentIndex === 0}
          icon={<span>←</span>}
        >
          Previous
        </Button>

        <div className="flex gap-1">
          {flashcards.map((_, i) => (
            <button
              key={i}
              onClick={() => { setCurrentIndex(i); setIsFlipped(false); setShowHint(false); }}
              className={`
                w-2 h-2 rounded-full transition-all
                ${i === currentIndex 
                  ? 'w-6 bg-indigo-500' 
                  : scores[i] !== undefined
                    ? 'bg-green-400'
                    : 'bg-gray-300 dark:bg-gray-600 hover:bg-gray-400'
                }
              `}
              aria-label={`Go to card ${i + 1}`}
            />
          ))}
        </div>

        <Button
          variant="ghost"
          onClick={nextCard}
          disabled={currentIndex === flashcards.length - 1}
          icon={<span>→</span>}
          iconPosition="right"
        >
          Next
        </Button>
      </div>

      {/* Citations */}
      {currentCard.citations && currentCard.citations.length > 0 && (
        <div className="mt-6">
          <CitationList
            citations={currentCard.citations}
            title="Sources"
            collapsible={true}
            defaultCollapsed={true}
            subjectId={subjectId}
          />
        </div>
      )}
    </div>
  );
}
