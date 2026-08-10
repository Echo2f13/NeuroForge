'use client';

import { useRef, useEffect, useState, useCallback } from 'react';
import { MindMap } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';

interface MindMapViewerProps {
  mindmap: MindMap | null;
  topic?: string;
}

interface NodePosition {
  id: string;
  x: number;
  y: number;
  label: string;
  type: string;
  parentId: string | null;
  level: number;
}

export function MindMapViewer({ mindmap, topic }: MindMapViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [positions, setPositions] = useState<NodePosition[]>([]);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  // Calculate node positions in a radial layout
  useEffect(() => {
    if (!mindmap || mindmap.nodes.length === 0) return;

    const centerX = 400;
    const centerY = 300;
    const levelRadius = 150;

    // Build tree structure
    const nodeMap = new Map(mindmap.nodes.map(n => [n.id, { ...n, children: [] as string[] }]));
    
    mindmap.nodes.forEach(node => {
      if (node.parent_id && nodeMap.has(node.parent_id)) {
        nodeMap.get(node.parent_id)!.children.push(node.id);
      }
    });

    // Find root (node with no parent)
    const root = mindmap.nodes.find(n => !n.parent_id);
    if (!root) return;

    // Calculate positions using radial layout
    const calculatedPositions: NodePosition[] = [];
    
    const layoutNode = (
      nodeId: string, 
      level: number, 
      startAngle: number, 
      endAngle: number,
      parentX?: number,
      parentY?: number
    ) => {
      const node = nodeMap.get(nodeId);
      if (!node) return;

      let x: number, y: number;
      
      if (level === 0) {
        // Root node at center
        x = centerX;
        y = centerY;
      } else {
        // Calculate position on arc
        const midAngle = (startAngle + endAngle) / 2;
        const radius = levelRadius * level;
        x = centerX + radius * Math.cos(midAngle);
        y = centerY + radius * Math.sin(midAngle);
      }

      calculatedPositions.push({
        id: node.id,
        x,
        y,
        label: node.label,
        type: node.type,
        parentId: node.parent_id,
        level,
      });

      // Layout children
      const children = node.children;
      if (children.length > 0) {
        const angleSpan = endAngle - startAngle;
        const childAngleStep = angleSpan / children.length;
        
        children.forEach((childId, index) => {
          const childStartAngle = startAngle + index * childAngleStep;
          const childEndAngle = childStartAngle + childAngleStep;
          layoutNode(childId, level + 1, childStartAngle, childEndAngle, x, y);
        });
      }
    };

    layoutNode(root.id, 0, 0, 2 * Math.PI);
    setPositions(calculatedPositions);
  }, [mindmap]);

  // Pan and zoom handlers
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setScale(prev => Math.max(0.5, Math.min(2, prev * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  }, [isDragging, dragStart]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const resetView = useCallback(() => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  }, []);

  const zoomIn = useCallback(() => {
    setScale(prev => Math.min(2, prev * 1.2));
  }, []);

  const zoomOut = useCallback(() => {
    setScale(prev => Math.max(0.5, prev * 0.8));
  }, []);

  if (!mindmap || mindmap.nodes.length === 0) {
    return (
      <EmptyState
        icon={EmptyState.icons.mindmap}
        title="No mind map"
        description="Generate a mind map for a topic to visualize concepts"
      />
    );
  }

  // Get node colors based on type/level
  const getNodeColor = (type: string, level: number) => {
    if (level === 0) return 'from-indigo-500 to-purple-500';
    if (type === 'subtopic') return 'from-blue-400 to-cyan-400';
    if (type === 'detail') return 'from-green-400 to-emerald-400';
    return 'from-gray-400 to-gray-500';
  };

  return (
    <div className="relative w-full">
      {/* Controls */}
      <div className="absolute top-4 right-4 z-10 flex gap-2">
        <Button variant="secondary" size="sm" onClick={zoomIn}>
          +
        </Button>
        <Button variant="secondary" size="sm" onClick={zoomOut}>
          −
        </Button>
        <Button variant="secondary" size="sm" onClick={resetView}>
          Reset
        </Button>
      </div>

      {/* Topic title */}
      {topic && (
        <div className="absolute top-4 left-4 z-10">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white bg-white/80 dark:bg-gray-800/80 px-3 py-1 rounded-lg backdrop-blur-sm">
            🗺️ {topic}
          </h3>
        </div>
      )}

      {/* Mind map canvas */}
      <Card className="overflow-hidden" padding="none">
        <div
          ref={containerRef}
          className="w-full h-[500px] bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 cursor-grab active:cursor-grabbing"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <svg
            width="100%"
            height="100%"
            style={{
              transform: `scale(${scale}) translate(${pan.x / scale}px, ${pan.y / scale}px)`,
              transformOrigin: 'center center',
            }}
          >
            {/* Draw edges first */}
            {positions.map(node => {
              if (!node.parentId) return null;
              const parent = positions.find(p => p.id === node.parentId);
              if (!parent) return null;

              return (
                <line
                  key={`edge-${node.id}`}
                  x1={parent.x}
                  y1={parent.y}
                  x2={node.x}
                  y2={node.y}
                  className="stroke-gray-300 dark:stroke-gray-600"
                  strokeWidth={2}
                  strokeDasharray={node.level > 2 ? '4 4' : undefined}
                />
              );
            })}

            {/* Draw nodes */}
            {positions.map(node => {
              const isSelected = selectedNode === node.id;
              const nodeSize = node.level === 0 ? 80 : node.level === 1 ? 60 : 50;
              
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={() => setSelectedNode(isSelected ? null : node.id)}
                  className="cursor-pointer"
                >
                  {/* Node background */}
                  <circle
                    r={nodeSize / 2}
                    className={`
                      fill-white dark:fill-gray-800 
                      ${isSelected ? 'stroke-indigo-500 stroke-[3]' : 'stroke-gray-200 dark:stroke-gray-700 stroke-2'}
                      transition-all duration-200 hover:stroke-indigo-400
                    `}
                    filter="url(#shadow)"
                  />
                  
                  {/* Colored indicator */}
                  <circle
                    r={nodeSize / 2 - 4}
                    className={`bg-gradient-to-br ${getNodeColor(node.type, node.level)}`}
                    fill={node.level === 0 ? 'url(#gradientRoot)' : node.level === 1 ? 'url(#gradientL1)' : 'url(#gradientL2)'}
                    opacity={0.15}
                  />

                  {/* Text */}
                  <text
                    textAnchor="middle"
                    dominantBaseline="middle"
                    className={`
                      fill-gray-800 dark:fill-gray-200 font-medium select-none pointer-events-none
                      ${node.level === 0 ? 'text-sm' : 'text-xs'}
                    `}
                  >
                    {node.label.length > 15 ? node.label.substring(0, 15) + '...' : node.label}
                  </text>
                </g>
              );
            })}

            {/* Gradient definitions */}
            <defs>
              <filter id="shadow" x="-50%" y="-50%" width="200%" height="200%">
                <feDropShadow dx="0" dy="2" stdDeviation="3" floodOpacity="0.15" />
              </filter>
              <linearGradient id="gradientRoot" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366f1" />
                <stop offset="100%" stopColor="#a855f7" />
              </linearGradient>
              <linearGradient id="gradientL1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#3b82f6" />
                <stop offset="100%" stopColor="#06b6d4" />
              </linearGradient>
              <linearGradient id="gradientL2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#22c55e" />
                <stop offset="100%" stopColor="#10b981" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </Card>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 justify-center text-sm">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500" />
          <span className="text-gray-600 dark:text-gray-400">Main Topic</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-gradient-to-r from-blue-400 to-cyan-400" />
          <span className="text-gray-600 dark:text-gray-400">Subtopic</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-full bg-gradient-to-r from-green-400 to-emerald-400" />
          <span className="text-gray-600 dark:text-gray-400">Detail</span>
        </div>
      </div>

      {/* Selected node details */}
      {selectedNode && (
        <Card className="mt-4 animate-fade-in" padding="md">
          <h4 className="font-medium text-gray-900 dark:text-white mb-2">
            {positions.find(p => p.id === selectedNode)?.label}
          </h4>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Level: {positions.find(p => p.id === selectedNode)?.level} | 
            Type: {positions.find(p => p.id === selectedNode)?.type}
          </p>
        </Card>
      )}

      {/* Instructions */}
      <p className="text-center text-xs text-gray-400 dark:text-gray-600 mt-4">
        Scroll to zoom • Drag to pan • Click nodes for details
      </p>
    </div>
  );
}
