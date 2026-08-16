'use client';

import { useState, useCallback } from 'react';
import { UploadStatus } from '@/lib/api';
import api from '@/lib/api';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { useCitation } from '@/contexts/CitationContext';

interface Document {
  id: string;
  filename: string;
  file_type: string;
  upload_date: string;
  chunk_count: number;
  concept_count: number;
}

interface DocumentsPanelProps {
  subjectId: string;
  subjectName: string;
  subjectColor: string;
  documents: Document[];
  onDocumentUploaded: () => void;
  loading?: boolean;
}

export function DocumentsPanel({
  subjectId,
  subjectName,
  subjectColor,
  documents,
  onDocumentUploaded,
  loading = false,
}: DocumentsPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadStatus | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileDrop = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    setUploading(true);
    setError(null);
    setUploadProgress(null);
    
    // Upload multiple files
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      try {
        const result = await api.uploadDocument(file, true, subjectId);
        
        if (result.status === 'processing') {
          await api.waitForUpload(
            result.document_id,
            (status) => setUploadProgress(status),
            1500
          );
        }
      } catch (err: any) {
        setError(err.message);
        break;
      }
    }
    
    setUploading(false);
    setTimeout(() => setUploadProgress(null), 2000);
    onDocumentUploaded();
  }, [subjectId, onDocumentUploaded]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFileDrop(e.dataTransfer.files);
  };

  const handleYouTubeUpload = async () => {
    const url = prompt('Enter YouTube URL:');
    if (!url) return;
    
    setUploading(true);
    setError(null);
    try {
      await api.uploadYouTube(url);
      onDocumentUploaded();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Area */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Add Study Materials
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Upload documents to <span style={{ color: subjectColor }} className="font-medium">{subjectName}</span>
          </p>
        </CardHeader>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg text-red-700 dark:text-red-400 text-sm">
              {error}
              <button onClick={() => setError(null)} className="ml-2 hover:text-red-900">×</button>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {/* File Upload Zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={`
                relative border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all duration-200
                ${isDragging 
                  ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20 scale-[1.02]' 
                  : 'border-gray-300 dark:border-gray-700 hover:border-indigo-400 dark:hover:border-indigo-600 hover:bg-gray-50 dark:hover:bg-gray-800/50'
                }
              `}
              style={isDragging ? { borderColor: subjectColor, backgroundColor: `${subjectColor}10` } : undefined}
            >
              <input
                type="file"
                className="absolute inset-0 opacity-0 cursor-pointer"
                accept=".pdf,.pptx,.docx,.png,.jpg,.jpeg,.txt,.md"
                onChange={(e) => handleFileDrop(e.target.files)}
                disabled={uploading}
                multiple
              />
              <div className="text-4xl mb-3">📄</div>
              <p className="font-medium text-gray-900 dark:text-white text-sm">Drop files or click to upload</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">PDF, PPTX, DOCX, Images, Text</p>
            </div>
            
            {/* YouTube Upload */}
            <button
              onClick={handleYouTubeUpload}
              disabled={uploading}
              className="border-2 border-dashed border-gray-300 dark:border-gray-700 rounded-xl p-6 text-center hover:border-red-400 dark:hover:border-red-600 hover:bg-red-50/50 dark:hover:bg-red-900/10 transition-all duration-200 disabled:opacity-50"
            >
              <div className="text-4xl mb-3">🎬</div>
              <p className="font-medium text-gray-900 dark:text-white text-sm">YouTube Video</p>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Extract from transcripts</p>
            </button>
          </div>
          
          {/* Upload Progress */}
          {uploadProgress && (
            <div className="mt-4 p-4 rounded-xl" style={{ backgroundColor: `${subjectColor}10` }}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm" style={{ color: subjectColor }}>{uploadProgress.message}</span>
                <span className="text-sm" style={{ color: subjectColor }}>{uploadProgress.progress}%</span>
              </div>
              <ProgressBar progress={uploadProgress.progress} />
              {uploadProgress.status === 'completed' && (
                <p className="mt-2 text-sm text-green-600 dark:text-green-400">
                  ✅ {uploadProgress.chunks_created} chunks, {uploadProgress.concepts_extracted} concepts
                </p>
              )}
            </div>
          )}
          
          {uploading && !uploadProgress && (
            <div className="mt-4 flex items-center justify-center gap-3" style={{ color: subjectColor }}>
              <LoadingSpinner size="sm" />
              <span className="text-sm">Processing...</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Documents List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Documents
            </h3>
            <Badge variant="default">{documents.length}</Badge>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <LoadingSpinner />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={EmptyState.icons.document}
              title="No documents yet"
              description="Upload your first document to start learning"
              variant="compact"
            />
          ) : (
            <div className="space-y-2">
              {documents.map((doc) => (
                <DocumentItem 
                  key={doc.id} 
                  document={doc} 
                  color={subjectColor}
                  subjectId={subjectId}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Document Item Component
function DocumentItem({ document, color, subjectId }: { document: Document; color: string; subjectId: string }) {
  const { openDocument } = useCitation();
  
  const fileTypeIcons: Record<string, string> = {
    pdf: '📕',
    pptx: '📊',
    docx: '📘',
    txt: '📝',
    md: '📝',
    youtube: '🎬',
    image: '🖼️',
  };

  const icon = fileTypeIcons[document.file_type] || '📄';
  const date = new Date(document.upload_date).toLocaleDateString();

  const handleViewDocument = () => {
    openDocument(subjectId, document.id);
  };

  return (
    <div className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors group">
      <div 
        className="w-10 h-10 rounded-lg flex items-center justify-center text-lg"
        style={{ backgroundColor: `${color}15` }}
      >
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium text-gray-900 dark:text-white text-sm truncate">
          {document.filename}
        </p>
        <p className="text-xs text-gray-500 dark:text-gray-400">
          {date} • {document.chunk_count} chunks • {document.concept_count} concepts
        </p>
      </div>
      <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
        <button 
          onClick={handleViewDocument}
          className="p-1.5 rounded hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
          title="View document"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
          </svg>
        </button>
      </div>
    </div>
  );
}

export type { Document };
