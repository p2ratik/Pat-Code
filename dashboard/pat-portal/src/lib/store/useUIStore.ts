import { create } from 'zustand';

interface UIState {
  isCreateAgentOpen: boolean;
  setCreateAgentOpen: (isOpen: boolean) => void;
  isAddToolOpen: boolean;
  setAddToolOpen: (isOpen: boolean) => void;
  isIntegrationsOpen: boolean;
  setIntegrationsOpen: (isOpen: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  isCreateAgentOpen: false,
  setCreateAgentOpen: (isOpen) => set({ isCreateAgentOpen: isOpen }),
  isAddToolOpen: false,
  setAddToolOpen: (isOpen) => set({ isAddToolOpen: isOpen }),
  isIntegrationsOpen: false,
  setIntegrationsOpen: (isOpen) => set({ isIntegrationsOpen: isOpen }),
}));
