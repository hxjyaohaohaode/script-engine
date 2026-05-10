import { create } from 'zustand'

export interface AgentStatus {
  name: string
  status: 'idle' | 'busy' | 'error' | 'offline'
  currentTask?: string
  queueCount: number
}

interface AgentState {
  agents: AgentStatus[]
  taskQueue: number
  setAgents: (agents: AgentStatus[]) => void
  updateAgent: (name: string, updates: Partial<AgentStatus>) => void
  setTaskQueue: (count: number) => void
}

const defaultAgents: AgentStatus[] = [
  { name: '编排Agent', status: 'idle', queueCount: 0 },
  { name: '创作Agent', status: 'idle', queueCount: 0 },
  { name: '审计Agent', status: 'idle', queueCount: 0 },
  { name: '状态Agent', status: 'idle', queueCount: 0 },
  { name: '素材Agent', status: 'idle', queueCount: 0 },
  { name: '伏笔Agent', status: 'idle', queueCount: 0 },
  { name: '创意Agent', status: 'idle', queueCount: 0 },
]

export const useAgentStore = create<AgentState>((set) => ({
  agents: defaultAgents,
  taskQueue: 0,
  setAgents: (agents) => set({ agents }),
  updateAgent: (name, updates) =>
    set((state) => ({
      agents: state.agents.map((a) => (a.name === name ? { ...a, ...updates } : a)),
    })),
  setTaskQueue: (count) => set({ taskQueue: count }),
}))
