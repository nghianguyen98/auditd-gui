import { createContext, useContext, useState, useEffect } from 'react';

const NodeContext = createContext();

export function NodeProvider({ children }) {
  const [selectedNodeId, setSelectedNodeId] = useState(() => {
    const saved = localStorage.getItem('auditvisual_node_id');
    return saved ? parseInt(saved, 10) : null;
  });

  useEffect(() => {
    if (selectedNodeId) {
      localStorage.setItem('auditvisual_node_id', selectedNodeId);
    } else {
      localStorage.removeItem('auditvisual_node_id');
    }
  }, [selectedNodeId]);

  return (
    <NodeContext.Provider value={{ selectedNodeId, setSelectedNodeId }}>
      {children}
    </NodeContext.Provider>
  );
}

export function useNodeContext() {
  return useContext(NodeContext);
}
