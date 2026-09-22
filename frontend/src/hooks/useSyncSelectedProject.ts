import { useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

/**
 * Keeps `selectedProjectId` (persisted, drives the top-bar selector) in
 * sync with the `:projectId` route param, so deep links and page refreshes
 * land on the right project without an extra step.
 */
export function useSyncSelectedProject() {
  const { projectId } = useParams();
  const setSelectedProjectId = useAuthStore((s) => s.setSelectedProjectId);

  useEffect(() => {
    if (projectId) {
      setSelectedProjectId(projectId);
    }
  }, [projectId, setSelectedProjectId]);
}
