import React, { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import {
  ReactFlow,
  Controls,
  Background,
  MiniMap,
  useNodesState,
  useEdgesState,
  Handle,
  Position
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Network,
  Bot,
  Server,
  Database,
  Layers,
  Cpu,
  RefreshCw,
  Info,
  X,
  Shield,
  Activity
} from 'lucide-react';

// Custom Node Components
const GatewayNode = ({ data }: any) => (
  <div className="p-3 bg-[#181C23] border-2 border-[#F0A43A] rounded shadow-xl font-mono text-xs w-60 text-left">
    <Handle type="target" position={Position.Left} className="w-2.5 h-2.5 bg-[#F0A43A]" />
    <div className="flex items-center gap-2 mb-1">
      <div className="w-5 h-5 rounded bg-[#F0A43A]/20 flex items-center justify-center text-[#F0A43A]">
        <Cpu className="w-3.5 h-3.5" />
      </div>
      <div className="font-bold text-[#ECEFF4] text-xs">{data.label}</div>
    </div>
    <div className="text-[10px] text-[#9DA7B5]">{data.subtitle}</div>
    <div className="mt-2 pt-2 border-t border-[#303640] flex items-center justify-between text-[10px]">
      <span className="text-[#43B581] font-bold">● {data.status}</span>
      <span className="text-[#F0A43A] bg-[#F0A43A]/10 px-1 rounded">{data.badge}</span>
    </div>
    <Handle type="source" position={Position.Right} className="w-2.5 h-2.5 bg-[#F0A43A]" />
    <Handle type="source" position={Position.Bottom} id="db" className="w-2.5 h-2.5 bg-[#303640]" />
  </div>
);

const AgentNode = ({ data }: any) => (
  <div className="p-3 bg-[#14171D] border border-[#F0A43A]/60 rounded shadow-md font-mono text-xs w-56 text-left">
    <div className="flex items-center gap-2 mb-1">
      <Bot className="w-4 h-4 text-[#F0A43A]" />
      <div className="font-bold text-[#ECEFF4] truncate">{data.label}</div>
    </div>
    <div className="text-[10px] text-[#9DA7B5]">{data.subtitle}</div>
    <div className="mt-2 text-[10px] text-[#626D7C] flex justify-between">
      <span>Runs: {data.orchestrations}</span>
      <span className="text-[#43B581]">Active</span>
    </div>
    <Handle type="source" position={Position.Right} className="w-2 h-2 bg-[#F0A43A]" />
  </div>
);

const ServerNode = ({ data }: any) => (
  <div className="p-3 bg-[#14171D] border border-[#48B9D0]/60 rounded shadow-md font-mono text-xs w-56 text-left">
    <Handle type="target" position={Position.Left} className="w-2 h-2 bg-[#48B9D0]" />
    <div className="flex items-center gap-2 mb-1">
      <Server className="w-4 h-4 text-[#48B9D0]" />
      <div className="font-bold text-[#ECEFF4] truncate">{data.label}</div>
    </div>
    <div className="text-[10px] text-[#9DA7B5]">{data.subtitle}</div>
    <div className="mt-2 pt-1 border-t border-[#303640] flex justify-between text-[10px]">
      <span className="text-[#43B581] font-bold">{data.status}</span>
      <span className="text-[#48B9D0]">{data.latency_ms} ms</span>
    </div>
    <Handle type="source" position={Position.Right} className="w-2 h-2 bg-[#43B581]" />
  </div>
);

const IntegrationNode = ({ data }: any) => (
  <div className="p-3 bg-[#101216] border border-[#43B581]/50 rounded shadow-md font-mono text-xs w-52 text-left">
    <Handle type="target" position={Position.Left} className="w-2 h-2 bg-[#43B581]" />
    <div className="flex items-center gap-2 mb-1">
      <Layers className="w-4 h-4 text-[#43B581]" />
      <div className="font-bold text-[#ECEFF4] truncate">{data.label}</div>
    </div>
    <div className="text-[10px] text-[#9DA7B5]">{data.subtitle}</div>
    <div className="mt-1 text-[9px] text-[#43B581]">SYNC NOMINAL</div>
  </div>
);

const DatabaseNode = ({ data }: any) => (
  <div className="p-3 bg-[#14171D] border border-[#303640] rounded shadow-md font-mono text-xs w-56 text-left">
    <Handle type="target" position={Position.Top} className="w-2 h-2 bg-[#303640]" />
    <div className="flex items-center gap-2 mb-1">
      <Database className="w-4 h-4 text-[#ECEFF4]" />
      <div className="font-bold text-[#ECEFF4]">{data.label}</div>
    </div>
    <div className="text-[10px] text-[#9DA7B5]">{data.subtitle}</div>
  </div>
);

const nodeTypes = {
  gatewayNode: GatewayNode,
  agentNode: AgentNode,
  serverNode: ServerNode,
  integrationNode: IntegrationNode,
  databaseNode: DatabaseNode,
};

export const InfrastructureMap: React.FC = () => {
  const [selectedNode, setSelectedNode] = useState<any>(null);

  const { data: topology, isLoading, refetch } = useQuery({
    queryKey: ['infrastructure-topology'],
    queryFn: () => api.getTopology(),
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    if (topology) {
      setNodes(topology.nodes);
      setEdges(topology.edges);
    }
  }, [topology, setNodes, setEdges]);

  const onNodeClick = (_: any, node: any) => {
    setSelectedNode(node);
  };

  return (
    <div className="space-y-4 font-mono h-[calc(100vh-130px)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#303640] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-[#ECEFF4]">
              INFRASTRUCTURE TOPOLOGY MAP
            </h1>
            <span className="text-[11px] px-2 py-0.5 rounded bg-[#48B9D0]/15 text-[#48B9D0] border border-[#48B9D0]/30">
              DISTRIBUTED GRAPH VISUALIZATION
            </span>
          </div>
          <p className="text-xs text-[#9DA7B5] mt-1 font-sans">
            Interactive topology showing AI agents, protocol gateway, connected MCP servers, and enterprise integrations.
          </p>
        </div>

        <button
          onClick={() => refetch()}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181C23] hover:bg-[#1F242D] border border-[#303640] text-xs text-[#ECEFF4] rounded"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh Topology
        </button>
      </div>

      {/* React Flow Graph Area */}
      <div className="flex-1 bg-[#101216] border border-[#303640] rounded relative overflow-hidden">
        {isLoading ? (
          <div className="h-full flex items-center justify-center text-xs text-[#9DA7B5]">
            Rendering infrastructure topology graph...
          </div>
        ) : (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            fitView
            className="bg-[#101216]"
          >
            <Background color="#303640" gap={20} size={1} />
            <Controls className="bg-[#181C23] border border-[#303640] text-[#ECEFF4]" />
            <MiniMap
              nodeColor={(n) => {
                if (n.type === 'gatewayNode') return '#F0A43A';
                if (n.type === 'agentNode') return '#F0A43A';
                if (n.type === 'serverNode') return '#48B9D0';
                if (n.type === 'integrationNode') return '#43B581';
                return '#303640';
              }}
              style={{ backgroundColor: '#14171D', borderColor: '#303640' }}
            />
          </ReactFlow>
        )}

        {/* Selected Node Inspector Drawer */}
        {selectedNode && (
          <div className="absolute right-4 top-4 w-80 bg-[#14171D] border border-[#303640] rounded shadow-2xl p-4 z-20 space-y-3">
            <div className="flex items-center justify-between border-b border-[#303640] pb-2 text-xs">
              <span className="font-bold text-[#ECEFF4] flex items-center gap-1.5">
                <Info className="w-4 h-4 text-[#F0A43A]" />
                Node Inspector
              </span>
              <button onClick={() => setSelectedNode(null)}>
                <X className="w-4 h-4 text-[#626D7C]" />
              </button>
            </div>
            <div className="space-y-2 text-xs">
              <div>
                <div className="text-[10px] text-[#626D7C]">NODE LABEL</div>
                <div className="font-bold text-[#ECEFF4] mt-0.5">{selectedNode.data.label}</div>
              </div>
              <div>
                <div className="text-[10px] text-[#626D7C]">TYPE</div>
                <div className="text-[#48B9D0] mt-0.5">{selectedNode.data.type}</div>
              </div>
              <div>
                <div className="text-[10px] text-[#626D7C]">STATUS</div>
                <div className="text-[#43B581] font-bold mt-0.5">{selectedNode.data.status || 'ONLINE'}</div>
              </div>
              {selectedNode.data.latency_ms && (
                <div>
                  <div className="text-[10px] text-[#626D7C]">AVERAGE LATENCY</div>
                  <div className="text-[#ECEFF4] mt-0.5">{selectedNode.data.latency_ms} ms</div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
