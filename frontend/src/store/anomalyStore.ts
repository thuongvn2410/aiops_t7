import { create } from 'zustand';
import type { AnomalyEvent } from '../api/websocket';

interface AnomalyState {
  alerts: AnomalyEvent[];
  lastCritical?: AnomalyEvent;
  dismissedCriticalId?: string;
  addAlert: (event: AnomalyEvent) => void;
  dismissCritical: () => void;
  setInitialAlerts: (events: AnomalyEvent[]) => void;
}

export const useAnomalyStore = create<AnomalyState>((set, get) => ({
  alerts: [],
  addAlert: (event) =>
    set((state) => {
      const merged = [event, ...state.alerts.filter((item) => item.event_id !== event.event_id)].slice(0, 100);
      return { alerts: merged, lastCritical: event.severity === 'critical' ? event : state.lastCritical };
    }),
  dismissCritical: () => set({ dismissedCriticalId: get().lastCritical?.event_id }),
  setInitialAlerts: (events) => set({ alerts: events.slice(0, 100) })
}));
