import { useCallback, useRef, useState } from 'react';
import { SSEPayload, Graph, Source } from '../types';

interface UseEventSourceReturn {
  sendQuery: (query: string, onUpdate: (text: string, sources?: Source[], graph?: Graph) => void) => void;
  isStreaming: boolean;
  error: string | null;
}

export const useEventSource = (apiUrl: string = 'http://localhost:8000'): UseEventSourceReturn => {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const sendQuery = useCallback((
    query: string, 
    onUpdate: (text: string, sources?: Source[], graph?: Graph) => void
  ) => {
    // Cancel any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    abortControllerRef.current = new AbortController();
    setIsStreaming(true);
    setError(null);

    let accumulatedText = '';
    let currentSources: Source[] = [];
    let currentGraph: Graph = { nodes: [], edges: [] };

    const fetchData = async () => {
      try {
        const response = await fetch(`${apiUrl}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ query }),
          signal: abortControllerRef.current?.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('No response body');
        }

        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const dataStr = line.slice(6); // Remove 'data: '
              
              if (dataStr === '[DONE]') {
                setIsStreaming(false);
                return;
              }

              try {
                const payload: SSEPayload = JSON.parse(dataStr);

                if (payload.error) {
                  throw new Error(payload.error);
                }

                switch (payload.type) {
                  case 'graph':
                    if (payload.nodes && payload.edges) {
                      currentGraph = {
                        nodes: payload.nodes,
                        edges: payload.edges,
                      };
                      onUpdate(accumulatedText, currentSources, currentGraph);
                    }
                    break;

                  case 'metadata':
                    if (payload.sources) {
                      currentSources = payload.sources;
                      onUpdate(accumulatedText, currentSources, currentGraph);
                    }
                    break;

                  case 'text':
                    if (payload.chunk) {
                      accumulatedText += payload.chunk;
                      onUpdate(accumulatedText, currentSources, currentGraph);
                    }
                    break;
                }
              } catch (parseError) {
                console.warn('Failed to parse SSE payload:', parseError);
              }
            }
          }
        }
      } catch (fetchError: any) {
        if (fetchError.name !== 'AbortError') {
          console.error('SSE Error:', fetchError);
          setError(fetchError.message || 'Failed to fetch data');
        }
      } finally {
        setIsStreaming(false);
      }
    };

    fetchData();
  }, [apiUrl]);

  return {
    sendQuery,
    isStreaming,
    error,
  };
};