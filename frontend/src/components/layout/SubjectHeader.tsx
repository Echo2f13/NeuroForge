'use client';

import { Subject, SubjectSummary } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

type FeatureTab = 'quiz' | 'flashcards' | 'notes' | 'chat' | 'mindmap' | 'documents';

interface SubjectHeaderProps {
  subject: Subject | SubjectSummary | null;
  activeTab: FeatureTab;
  onTabChange: (tab: FeatureTab) => void;
  onEditSubject?: () => void;
  stats?: {
    documents: number;
    quizzes: number;
    mastery: number;
    streak: number;
  };
}

const FEATURE_TABS: { id: FeatureTab; label: string; icon: string; shortcut: string }[] = [
  { id: 'documents', label: 'Documents', icon: '📄', shortcut: '1' },
  { id: 'quiz', label: 'Quiz', icon: '📝', shortcut: '2' },
  { id: 'flashcards', label: 'Flashcards', icon: '🎴', shortcut: '3' },
  { id: 'notes', label: 'Notes', icon: '📖', shortcut: '4' },
  { id: 'chat', label: 'AI Tutor', icon: '💬', shortcut: '5' },
  { id: 'mindmap', label: 'Mind Map', icon: '🗺️', shortcut: '6' },
];

export function SubjectHeader({
  subject,
  activeTab,
  onTabChange,
  onEditSubject,
  stats,
}: SubjectHeaderProps) {
  const subjectColor = subject?.color || '#6366f1';
  const subjectName = subject?.name || 'General';
  const subjectIcon = subject?.icon || '📚';
  const subjectDescription = (subject as Subject)?.description;

  return (
    <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
      {/* Subject Info */}
      <div 
        className="px-6 py-5"
        style={{ 
          background: `linear-gradient(135deg, ${subjectColor}08 0%, ${subjectColor}03 100%)`,
          borderBottom: `2px solid ${subjectColor}20`
        }}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-4">
            {/* Subject Icon */}
            <div 
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl shadow-lg"
              style={{ 
                backgroundColor: `${subjectColor}15`,
                boxShadow: `0 4px 14px ${subjectColor}20`
              }}
            >
              {subjectIcon}
            </div>
            
            {/* Subject Details */}
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {subjectName}
                </h1>
                {onEditSubject && subject?.id !== 'general' && (
                  <button
                    onClick={onEditSubject}
                    className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    title="Edit subject"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                  </button>
                )}
              </div>
              {subjectDescription && (
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 max-w-xl">
                  {subjectDescription}
                </p>
              )}
            </div>
          </div>

          {/* Subject Stats */}
          {stats && (
            <div className="flex items-center gap-6">
              <StatItem 
                icon="📄" 
                value={stats.documents} 
                label="Documents" 
                color={subjectColor}
              />
              <StatItem 
                icon="📝" 
                value={stats.quizzes} 
                label="Quizzes" 
                color={subjectColor}
              />
              <StatItem 
                icon="🎯" 
                value={`${stats.mastery}%`} 
                label="Mastery" 
                color={subjectColor}
              />
              {stats.streak > 0 && (
                <StatItem 
                  icon="🔥" 
                  value={stats.streak} 
                  label="Streak" 
                  color="#f97316"
                />
              )}
            </div>
          )}
        </div>
      </div>

      {/* Feature Tabs */}
      <div className="px-6">
        <nav className="flex gap-1 -mb-px overflow-x-auto scrollbar-hide">
          {FEATURE_TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`
                flex items-center gap-2 px-4 py-3 text-sm font-medium
                border-b-2 transition-all duration-150 whitespace-nowrap
                ${activeTab === tab.id
                  ? 'border-current text-gray-900 dark:text-white'
                  : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600'
                }
              `}
              style={activeTab === tab.id ? { color: subjectColor, borderColor: subjectColor } : undefined}
              title={`Press ${tab.shortcut}`}
            >
              <span>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}

// Stat Item Component
function StatItem({ 
  icon, 
  value, 
  label, 
  color 
}: { 
  icon: string; 
  value: number | string; 
  label: string; 
  color: string;
}) {
  return (
    <div className="text-center">
      <div className="flex items-center gap-1.5 justify-center">
        <span className="text-sm">{icon}</span>
        <span 
          className="text-xl font-bold"
          style={{ color }}
        >
          {value}
        </span>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  );
}

export type { FeatureTab };
