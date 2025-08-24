import React, { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink, FileText, BookOpen } from 'lucide-react';
import { Source } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';

interface SourcesProps {
  sources: Source[];
  className?: string;
}

export const Sources: React.FC<SourcesProps> = ({ sources, className = '' }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());

  // Remove duplicate sources based on paper_id and chunk_text
  const uniqueSources = sources.filter((source, index, self) => 
    index === self.findIndex(s => s.paper_id === source.paper_id && s.chunk_text === source.chunk_text)
  );

  if (uniqueSources.length === 0) return null;

  const toggleSourceExpansion = (sourceId: string) => {
    const newExpanded = new Set(expandedSources);
    if (newExpanded.has(sourceId)) {
      newExpanded.delete(sourceId);
    } else {
      newExpanded.add(sourceId);
    }
    setExpandedSources(newExpanded);
  };

  return (
    <div className={`mt-6 ${className}`}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex items-center gap-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors"
      >
        <BookOpen size={16} />
        Sources ({uniqueSources.length})
        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>

      {isExpanded && (
        <div className="mt-4 space-y-4">
          {uniqueSources.map((source, index) => {
            const sourceId = `${source.paper_id}-${index}`;
            const isSourceExpanded = expandedSources.has(sourceId);
            
            return (
            <div
              key={sourceId}
              className="border border-gray-200 dark:border-gray-700 rounded-xl p-5 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-900/50 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1 min-w-0 space-y-2">
                  <h4 className="font-semibold text-gray-900 dark:text-gray-100 text-base leading-tight">
                    {source.paper_title}
                  </h4>
                  <a
                    href={source.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 transition-colors font-medium"
                  >
                    <ExternalLink size={14} />
                    View PDF
                  </a>
                </div>
                <button
                  onClick={() => toggleSourceExpansion(sourceId)}
                  className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors flex-shrink-0 px-2 py-1 rounded-md hover:bg-gray-200 dark:hover:bg-gray-700"
                >
                  {isSourceExpanded ? 'Collapse' : 'Expand'}
                  {isSourceExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                </button>
              </div>
              
              <div className={`transition-all duration-200 ${isSourceExpanded ? 'max-h-none' : 'max-h-20 overflow-hidden'}`}>
                <div className="relative">
                  <div className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed bg-white dark:bg-gray-900/50 rounded-lg p-4 border border-gray-100 dark:border-gray-700">
                    <MarkdownRenderer content={source.chunk_text} />
                  </div>
                  {!isSourceExpanded && source.chunk_text.length > 200 && (
                    <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-white dark:from-gray-900/50 to-transparent rounded-b-lg" />
                  )}
                </div>
              </div>
            </div>
            );
          })}
        </div>
      )}
    </div>
  );
};