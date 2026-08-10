'use client';

import { useState } from 'react';
import { SubjectSummary } from '@/lib/api';
import { useTheme, ThemeToggle } from '@/contexts/ThemeContext';
import { Badge } from '@/components/ui/Badge';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface SidebarProps {
  subjects: SubjectSummary[];
  activeSubjectId: string;
  onSelectSubject: (subjectId: string) => void;
  onCreateSubject: () => void;
  onNavigate: (view: 'upload' | 'dashboard' | 'settings') => void;
  currentView: string;
  loading?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export function Sidebar({
  subjects,
  activeSubjectId,
  onSelectSubject,
  onCreateSubject,
  onNavigate,
  currentView,
  loading = false,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const [showArchived, setShowArchived] = useState(false);
  
  const activeSubjects = subjects.filter(s => s.status !== 'archived');
  const archivedSubjects = subjects.filter(s => s.status === 'archived');

  return (
    <aside className={`
      flex flex-col h-full bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800
      transition-all duration-300 ease-in-out
      ${collapsed ? 'w-16' : 'w-64'}
    `}>
      {/* Logo & Collapse Toggle */}
      <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-800">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">N</span>
            </div>
            <span className="font-bold text-gray-900 dark:text-white">NeuroForge</span>
          </div>
        )}
        {collapsed && (
          <div className="w-8 h-8 mx-auto bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">N</span>
          </div>
        )}
        {onToggleCollapse && !collapsed && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"
            title="Collapse sidebar"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* Subjects Section */}
      <div className="flex-1 overflow-y-auto py-4">
        {!collapsed && (
          <div className="px-4 mb-2">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Subjects
            </span>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner size="sm" />
          </div>
        ) : (
          <nav className="space-y-1 px-2">
            {/* General/All Subject */}
            <SidebarSubjectItem
              subject={{
                id: 'general',
                name: 'General',
                icon: '📚',
                color: '#6366f1',
                document_count: 0,
                status: 'active',
                description: null,
                is_default: true,
                chunk_count: 0,
                concept_count: 0,
                quiz_count: 0,
                average_score: 0,
                mastery_percent: 0,
                last_activity_at: null,
              }}
              isActive={activeSubjectId === 'general'}
              onClick={() => onSelectSubject('general')}
              collapsed={collapsed}
            />

            {/* Active Subjects */}
            {activeSubjects.map((subject) => (
              <SidebarSubjectItem
                key={subject.id}
                subject={subject}
                isActive={activeSubjectId === subject.id}
                onClick={() => onSelectSubject(subject.id)}
                collapsed={collapsed}
              />
            ))}

            {/* New Subject Button */}
            <button
              onClick={onCreateSubject}
              className={`
                w-full flex items-center gap-3 px-3 py-2 rounded-lg
                text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800
                transition-colors duration-150
                ${collapsed ? 'justify-center' : ''}
              `}
              title="Create new subject"
            >
              <span className="text-lg">➕</span>
              {!collapsed && <span className="text-sm">New Subject</span>}
            </button>

            {/* Archived Subjects Toggle */}
            {archivedSubjects.length > 0 && !collapsed && (
              <button
                onClick={() => setShowArchived(!showArchived)}
                className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg 
                  className={`w-3 h-3 transition-transform ${showArchived ? 'rotate-90' : ''}`} 
                  fill="none" stroke="currentColor" viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
                Archived ({archivedSubjects.length})
              </button>
            )}

            {/* Archived Subjects */}
            {showArchived && archivedSubjects.map((subject) => (
              <SidebarSubjectItem
                key={subject.id}
                subject={subject}
                isActive={activeSubjectId === subject.id}
                onClick={() => onSelectSubject(subject.id)}
                collapsed={collapsed}
                archived
              />
            ))}
          </nav>
        )}
      </div>

      {/* Quick Actions */}
      <div className="border-t border-gray-100 dark:border-gray-800 py-4 px-2">
        {!collapsed && (
          <div className="px-2 mb-2">
            <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
              Quick Access
            </span>
          </div>
        )}
        
        <nav className="space-y-1">
          <SidebarNavItem
            icon="📤"
            label="Upload"
            isActive={currentView === 'upload'}
            onClick={() => onNavigate('upload')}
            collapsed={collapsed}
          />
          <SidebarNavItem
            icon="📊"
            label="Dashboard"
            isActive={currentView === 'dashboard'}
            onClick={() => onNavigate('dashboard')}
            collapsed={collapsed}
          />
        </nav>
      </div>

      {/* Footer */}
      <div className="border-t border-gray-100 dark:border-gray-800 p-3 flex items-center justify-between">
        {!collapsed && <ThemeToggle />}
        {collapsed && (
          <div className="w-full flex justify-center">
            <ThemeToggle />
          </div>
        )}
        {onToggleCollapse && collapsed && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500 mx-auto"
            title="Expand sidebar"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            </svg>
          </button>
        )}
      </div>
    </aside>
  );
}


// Subject Item Component
function SidebarSubjectItem({
  subject,
  isActive,
  onClick,
  collapsed,
  archived = false,
}: {
  subject: SubjectSummary;
  isActive: boolean;
  onClick: () => void;
  collapsed: boolean;
  archived?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-3 py-2.5 rounded-lg
        transition-all duration-150 group relative
        ${isActive 
          ? 'bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/30 dark:to-purple-900/30' 
          : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
        }
        ${archived ? 'opacity-60' : ''}
        ${collapsed ? 'justify-center' : ''}
      `}
      title={collapsed ? subject.name : undefined}
    >
      {/* Color indicator */}
      <div 
        className={`
          absolute left-0 top-1/2 -translate-y-1/2 w-1 rounded-r-full transition-all
          ${isActive ? 'h-8' : 'h-0 group-hover:h-4'}
        `}
        style={{ backgroundColor: subject.color || '#6366f1' }}
      />
      
      {/* Icon */}
      <span className={`text-lg ${collapsed ? '' : 'ml-1'}`}>
        {subject.icon || '📚'}
      </span>
      
      {/* Name & Count */}
      {!collapsed && (
        <div className="flex-1 flex items-center justify-between min-w-0">
          <span className={`
            text-sm font-medium truncate
            ${isActive ? 'text-indigo-700 dark:text-indigo-300' : 'text-gray-700 dark:text-gray-300'}
          `}>
            {subject.name}
          </span>
          {subject.document_count > 0 && (
            <Badge variant="default" size="sm">
              {subject.document_count}
            </Badge>
          )}
        </div>
      )}
    </button>
  );
}

// Nav Item Component
function SidebarNavItem({
  icon,
  label,
  isActive,
  onClick,
  collapsed,
}: {
  icon: string;
  label: string;
  isActive: boolean;
  onClick: () => void;
  collapsed: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-3 py-2 rounded-lg
        transition-colors duration-150
        ${isActive 
          ? 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-white' 
          : 'text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50'
        }
        ${collapsed ? 'justify-center' : ''}
      `}
      title={collapsed ? label : undefined}
    >
      <span className="text-lg">{icon}</span>
      {!collapsed && <span className="text-sm font-medium">{label}</span>}
    </button>
  );
}
