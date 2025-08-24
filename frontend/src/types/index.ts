export interface GraphNode {
  id: string;
  type: string;
  name?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface Source {
  paper_id: string;
  paper_title: string;
  pdf_url: string;
  chunk_text: string;
}

export interface Message {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  graph?: Graph;
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface SSEPayload {
  type: 'graph' | 'metadata' | 'text';
  nodes?: GraphNode[];
  edges?: GraphEdge[];
  sources?: Source[];
  chunk?: string;
  error?: string;
}