'use client';

import { useState, useCallback, useEffect } from 'react';
import { QuizQuestion } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { ProgressBar, CircularProgress } from '@/components/ui/ProgressBar';
import { EmptyState } from '@/components/ui/EmptyState';
import { CitationList } from '@/components/citations';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';

interface QuizSessionProps {
  questions: QuizQuestion[];
  subjectId?: string;
  onComplete?: (score: number, total: number) => void;
}

export function QuizSession({ questions, subjectId, onComplete }: QuizSessionProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<string | null>(null);
  const [showExplanation, setShowExplanation] = useState(false);
  const [score, setScore] = useState(0);
  const [answers, setAnswers] = useState<(string | null)[]>([]);
  const [isComplete, setIsComplete] = useState(false);

  const currentQuestion = questions[currentIndex];
  const progress = ((currentIndex + 1) / questions.length) * 100;
  const isCorrect = selectedAnswer === currentQuestion?.correct_answer;

  // Reset state when questions change
  useEffect(() => {
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setShowExplanation(false);
    setScore(0);
    setAnswers([]);
    setIsComplete(false);
  }, [questions]);

  const handleAnswer = useCallback((answer: string) => {
    if (showExplanation) return;
    
    setSelectedAnswer(answer);
    setShowExplanation(true);
    setAnswers(prev => [...prev, answer]);
    
    if (answer === currentQuestion.correct_answer) {
      setScore(prev => prev + 1);
    }
  }, [showExplanation, currentQuestion?.correct_answer]);

  const nextQuestion = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(prev => prev + 1);
      setSelectedAnswer(null);
      setShowExplanation(false);
    } else {
      setIsComplete(true);
      onComplete?.(score + (isCorrect ? 0 : 0), questions.length);
    }
  }, [currentIndex, questions.length, score, isCorrect, onComplete]);

  const restartQuiz = useCallback(() => {
    setCurrentIndex(0);
    setSelectedAnswer(null);
    setShowExplanation(false);
    setScore(0);
    setAnswers([]);
    setIsComplete(false);
  }, []);

  // Keyboard shortcuts
  useKeyboardShortcuts([
    { key: '1', handler: () => currentQuestion?.options?.[0] && handleAnswer(currentQuestion.options[0]) },
    { key: '2', handler: () => currentQuestion?.options?.[1] && handleAnswer(currentQuestion.options[1]) },
    { key: '3', handler: () => currentQuestion?.options?.[2] && handleAnswer(currentQuestion.options[2]) },
    { key: '4', handler: () => currentQuestion?.options?.[3] && handleAnswer(currentQuestion.options[3]) },
    { key: 'Enter', ctrl: true, handler: () => showExplanation && nextQuestion() },
    { key: 'ArrowRight', handler: () => showExplanation && nextQuestion() },
  ]);

  if (questions.length === 0) {
    return (
      <EmptyState
        icon={EmptyState.icons.quiz}
        title="No quiz questions"
        description="Generate a quiz for a topic to test your knowledge"
      />
    );
  }

  // Quiz completed view
  if (isComplete) {
    const percentage = Math.round((score / questions.length) * 100);
    const grade = percentage >= 90 ? 'A' : percentage >= 80 ? 'B' : percentage >= 70 ? 'C' : percentage >= 60 ? 'D' : 'F';
    const message = percentage >= 90 ? 'Excellent work! 🎉' : 
                    percentage >= 70 ? 'Good job! Keep it up! 💪' : 
                    percentage >= 50 ? 'Not bad, but there\'s room for improvement 📚' :
                    'Keep studying, you\'ll get there! 💡';

    return (
      <Card className="max-w-lg mx-auto text-center" padding="lg">
        <div className="text-6xl mb-4">
          {percentage >= 90 ? '🏆' : percentage >= 70 ? '⭐' : percentage >= 50 ? '📝' : '📚'}
        </div>
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
          Quiz Complete!
        </h2>
        <p className="text-gray-600 dark:text-gray-400 mb-6">{message}</p>

        <div className="flex justify-center mb-6">
          <CircularProgress progress={percentage} size={120} color={percentage >= 70 ? 'success' : percentage >= 50 ? 'warning' : 'error'} />
        </div>

        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-xl">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{score}</p>
            <p className="text-sm text-gray-500">Correct</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-xl">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{questions.length - score}</p>
            <p className="text-sm text-gray-500">Incorrect</p>
          </div>
          <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-xl">
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{grade}</p>
            <p className="text-sm text-gray-500">Grade</p>
          </div>
        </div>

        <div className="flex gap-3 justify-center">
          <Button variant="secondary" onClick={restartQuiz}>
            Try Again
          </Button>
          <Button variant="primary">
            Review Answers
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <div className="flex items-center gap-3">
          <Badge variant="info">
            Question {currentIndex + 1} / {questions.length}
          </Badge>
          <Badge variant={currentQuestion.difficulty === 'easy' ? 'success' : currentQuestion.difficulty === 'hard' ? 'error' : 'warning'}>
            {currentQuestion.difficulty}
          </Badge>
        </div>
        <Badge variant="success" dot>
          Score: {score}
        </Badge>
      </div>

      {/* Progress */}
      <ProgressBar progress={progress} size="sm" className="mb-6" />

      {/* Question Card */}
      <Card className="mb-6" padding="lg">
        <div className="flex items-start gap-3 mb-6">
          <span className="text-2xl">
            {currentQuestion.question_type === 'mcq' ? '📋' : 
             currentQuestion.question_type === 'true_false' ? '✅' : '✍️'}
          </span>
          <h3 className="text-lg font-medium text-gray-900 dark:text-white leading-relaxed">
            {currentQuestion.question}
          </h3>
        </div>

        {/* MCQ Options */}
        {currentQuestion.question_type === 'mcq' && currentQuestion.options && (
          <div className="space-y-3">
            {currentQuestion.options.map((option, idx) => {
              const isSelected = selectedAnswer === option;
              const isCorrectOption = option === currentQuestion.correct_answer;
              
              let buttonClass = 'w-full p-4 text-left rounded-xl border-2 transition-all duration-200 ';
              
              if (showExplanation) {
                if (isCorrectOption) {
                  buttonClass += 'border-green-500 bg-green-50 dark:bg-green-900/20 text-green-800 dark:text-green-200';
                } else if (isSelected && !isCorrectOption) {
                  buttonClass += 'border-red-500 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200';
                } else {
                  buttonClass += 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-500';
                }
              } else {
                buttonClass += isSelected 
                  ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-indigo-300 dark:hover:border-indigo-700 hover:bg-gray-50 dark:hover:bg-gray-800';
              }

              return (
                <button
                  key={idx}
                  onClick={() => handleAnswer(option)}
                  disabled={showExplanation}
                  className={buttonClass}
                >
                  <div className="flex items-center gap-3">
                    <span className="w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-sm font-medium">
                      {String.fromCharCode(65 + idx)}
                    </span>
                    <span className="flex-1">{option}</span>
                    {showExplanation && isCorrectOption && (
                      <span className="text-green-500">✓</span>
                    )}
                    {showExplanation && isSelected && !isCorrectOption && (
                      <span className="text-red-500">✗</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {/* True/False Options */}
        {currentQuestion.question_type === 'true_false' && (
          <div className="flex gap-4 justify-center">
            {['True', 'False'].map((option) => {
              const isSelected = selectedAnswer === option;
              const isCorrectOption = option === currentQuestion.correct_answer;
              
              return (
                <Button
                  key={option}
                  variant={showExplanation 
                    ? isCorrectOption ? 'success' : isSelected ? 'danger' : 'secondary'
                    : isSelected ? 'primary' : 'secondary'
                  }
                  size="lg"
                  onClick={() => handleAnswer(option)}
                  disabled={showExplanation}
                  className="min-w-[120px]"
                >
                  {option === 'True' ? '✓ True' : '✗ False'}
                </Button>
              );
            })}
          </div>
        )}

        {/* Explanation */}
        {showExplanation && (
          <div className={`mt-6 p-4 rounded-xl ${isCorrect ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800' : 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'}`}>
            <div className="flex items-start gap-3">
              <span className="text-xl">{isCorrect ? '🎉' : '💡'}</span>
              <div>
                <p className={`font-medium mb-2 ${isCorrect ? 'text-green-800 dark:text-green-200' : 'text-blue-800 dark:text-blue-200'}`}>
                  {isCorrect ? 'Correct!' : `Incorrect. The answer is: ${currentQuestion.correct_answer}`}
                </p>
                <p className="text-gray-700 dark:text-gray-300">
                  {currentQuestion.explanation}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Citations */}
        {showExplanation && currentQuestion.citations && currentQuestion.citations.length > 0 && (
          <div className="mt-4">
            <CitationList
              citations={currentQuestion.citations}
              title="Sources"
              collapsible={true}
              defaultCollapsed={true}
              subjectId={subjectId}
            />
          </div>
        )}
      </Card>

      {/* Navigation */}
      {showExplanation && (
        <div className="flex justify-end">
          <Button onClick={nextQuestion} size="lg">
            {currentIndex < questions.length - 1 ? 'Next Question →' : '🎉 Finish Quiz'}
          </Button>
        </div>
      )}

      {/* Keyboard hint */}
      <p className="text-center text-xs text-gray-400 dark:text-gray-600 mt-4">
        Press 1-4 to select answer • Enter to continue
      </p>
    </div>
  );
}
