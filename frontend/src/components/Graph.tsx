import React, { useEffect, useRef, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { Graph as GraphType } from '../types';

interface GraphProps {
  graph: GraphType;
  className?: string;
}

export const Graph: React.FC<GraphProps> = ({ graph, className = '' }) => {
  const forceRef = useRef<any>(null);
  const [selectedNode, setSelectedNode] = React.useState<any>(null);
  const [hoveredNode, setHoveredNode] = React.useState<any>(null);

  // Transform data for react-force-graph-2d
  const graphData = useMemo(() => {
    const links = graph.edges.map(edge => ({
      source: edge.source,
      target: edge.target,
      type: edge.type,
    }));

    const nodes = graph.nodes.map(node => ({
      id: node.id,
      name: node.id,
      type: node.type,
      val: 8, // Node size
      color: getNodeColor(node),
    }));

    return { nodes, links };
  }, [graph]);

  useEffect(() => {
    if (forceRef.current) {
      // Configure forces for better layout
      forceRef.current
        .d3Force('charge')
        .strength(-300)
        .distanceMax(200);
      
      forceRef.current
        .d3Force('link')
        .distance(80)
        .strength(0.5);
        
      forceRef.current.d3ReheatSimulation();
    }
  }, [graph]);

  const getNodeColor = (node: any) => {
    const colors: { [key: string]: string } = {
      'Person': '#3B82F6',      // Blue
      'Organization': '#10B981', // Emerald
      'Concept': '#F59E0B',      // Amber
      'Location': '#EF4444',     // Red
      'Method': '#8B5CF6',       // Violet
      'Technology': '#06B6D4',   // Cyan
      'Theory': '#F97316',       // Orange
      'default': '#6B7280',      // Gray
    };
    return colors[node.type] || colors.default;
  };

  const getLinkColor = (link: any) => {
    if (hoveredNode && (link.source.id === hoveredNode.id || link.target.id === hoveredNode.id)) {
      return '#3B82F6';
    }
    return '#D1D5DB';
  };

  const getNodeSize = (node: any) => {
    if (selectedNode && node.id === selectedNode.id) return 12;
    if (hoveredNode && node.id === hoveredNode.id) return 10;
    return 8;
  };

  const getNodeOpacity = (node: any) => {
    if (!hoveredNode) return 1;
    if (node.id === hoveredNode.id) return 1;
    
    // Check if node is connected to hovered node
    const isConnected = graph.edges.some(edge => 
      (edge.source === hoveredNode.id && edge.target === node.id) ||
      (edge.target === hoveredNode.id && edge.source === node.id)
    );
    
    return isConnected ? 0.8 : 0.3;
  };

  if (graph.nodes.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 ${className}`}>
        <div className="text-center">
          <div className="w-20 h-20 mx-auto mb-6 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900/30 dark:to-purple-900/30 flex items-center justify-center shadow-lg">
            <svg className="w-10 h-10 text-blue-500 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
            Knowledge Graph
          </h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs mx-auto leading-relaxed">
            Interactive visualization of concepts and relationships will appear here as you explore research
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`relative bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 ${className}`}>
      {/* Graph Info Panel */}
      <div className="absolute top-4 left-4 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm rounded-xl p-4 z-10 shadow-lg border border-gray-200/50 dark:border-gray-700/50">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3 flex items-center gap-2">
          <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
          Knowledge Graph
        </h3>
        <div className="text-xs text-gray-600 dark:text-gray-400 space-y-2">
          <div className="flex items-center justify-between">
            <span>Nodes:</span>
            <span className="font-medium text-gray-900 dark:text-gray-100">{graph.nodes.length}</span>
          </div>
          <div className="flex items-center justify-between">
            <span>Edges:</span>
            <span className="font-medium text-gray-900 dark:text-gray-100">{graph.edges.length}</span>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute top-4 right-4 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm rounded-xl p-4 z-10 shadow-lg border border-gray-200/50 dark:border-gray-700/50">
        <h4 className="text-xs font-semibold text-gray-900 dark:text-gray-100 mb-3">Node Types</h4>
        <div className="space-y-2 text-xs">
          {['Person', 'Organization', 'Concept', 'Method', 'Technology', 'Theory'].map(type => (
            <div key={type} className="flex items-center gap-2">
              <div 
                className="w-3 h-3 rounded-full" 
                style={{ backgroundColor: getNodeColor({ type }) }}
              />
              <span className="text-gray-600 dark:text-gray-400">{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Selected Node Info */}
      {selectedNode && (
        <div className="absolute bottom-4 left-4 bg-white/95 dark:bg-gray-900/95 backdrop-blur-sm rounded-xl p-4 z-10 shadow-lg border border-gray-200/50 dark:border-gray-700/50 max-w-xs">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">
            {selectedNode.name}
          </h4>
          <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
            <div>Type: <span className="font-medium">{selectedNode.type}</span></div>
            <div>Connections: <span className="font-medium">
              {graph.edges.filter(edge => 
                edge.source === selectedNode.id || edge.target === selectedNode.id
              ).length}
            </span></div>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            className="mt-2 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300"
          >
            Close
          </button>
        </div>
      )}
      
      <ForceGraph2D
        ref={forceRef}
        graphData={graphData}
        nodeLabel={(node: any) => `${node.name} (${node.type})`}
        nodeColor={(node: any) => node.color}
        nodeVal={getNodeSize}
        nodeOpacity={getNodeOpacity}
        linkColor={getLinkColor}
        nodeRelSize={6}
        linkWidth={(link: any) => hoveredNode && (link.source.id === hoveredNode.id || link.target.id === hoveredNode.id) ? 3 : 1}
        linkDirectionalParticles={(link: any) => hoveredNode && (link.source.id === hoveredNode.id || link.target.id === hoveredNode.id) ? 4 : 0}
        linkDirectionalParticleWidth={3}
        linkDirectionalParticleSpeed={0.006}
        onNodeHover={(node) => {
          setHoveredNode(node);
          if (forceRef.current) {
            forceRef.current.nodeColor(forceRef.current.nodeColor());
          }
        }}
        onNodeClick={(node) => {
          setSelectedNode(node);
          if (forceRef.current) {
            // Center the view on the clicked node
            forceRef.current.centerAt(node.x, node.y, 1000);
            forceRef.current.zoom(2, 1000);
          }
        }}
        onLinkHover={(link) => {
          // Optional: Add link hover effects
        }}
        cooldownTicks={200}
        onEngineStop={() => {
          if (forceRef.current) {
            forceRef.current.zoomToFit(400, 50);
          }
        }}
        backgroundColor="transparent"
        linkHoverPrecision={8}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
      />
    </div>
  );
};