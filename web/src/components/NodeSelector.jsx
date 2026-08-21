import { useState, useEffect } from 'react';
import { apiGet } from '../api/client';
import { useNodeContext } from '../NodeContext';
import { Server, ServerCrash } from 'lucide-react';

export default function NodeSelector() {
  const [nodes, setNodes] = useState([]);
  const { selectedNodeId, setSelectedNodeId } = useNodeContext();

  useEffect(() => {
    async function loadNodes() {
      try {
        const data = await apiGet('/nodes');
        setNodes(data);
        
        // If there is a selected node but it's not in the list (e.g. deleted/recreated DB), clear it
        if (selectedNodeId && !data.find(n => n.id === selectedNodeId)) {
          setSelectedNodeId(null);
        }
      } catch (err) {
        console.error('Failed to load nodes:', err);
      }
    }
    loadNodes();
    
    // Poll nodes every 30s to update status
    const interval = setInterval(loadNodes, 30000);
    return () => clearInterval(interval);
  }, [selectedNodeId, setSelectedNodeId]);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--bg-elevated)', padding: '6px 12px', borderRadius: 8, border: '1px solid var(--glass-border)' }}>
      <Server size={16} color="var(--text-secondary)" />
      <select 
        value={selectedNodeId || ''} 
        onChange={(e) => setSelectedNodeId(e.target.value ? parseInt(e.target.value, 10) : null)}
        style={{
          background: 'transparent',
          border: 'none',
          color: 'var(--text)',
          outline: 'none',
          fontSize: '0.9rem',
          cursor: 'pointer'
        }}
      >
        <option value="">All Servers</option>
        {nodes.map(node => (
          <option key={node.id} value={node.id}>
            {node.hostname} {node.status === 'offline' ? '(Offline)' : ''}
          </option>
        ))}
      </select>
      {selectedNodeId && (
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: nodes.find(n => n.id === selectedNodeId)?.status === 'online' ? '#22c55e' : '#ef4444'
        }} title="Status" />
      )}
    </div>
  );
}
