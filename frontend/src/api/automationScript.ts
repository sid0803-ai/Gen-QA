import { api } from './client';
import type {
  AutomationScript,
  AutomationScriptGenerateInput,
  AutomationScriptUpdateInput,
  ScriptVersionSummary,
} from './types';

/** 404s when no script has been generated yet for this test case — callers handle that themselves. */
export function getAutomationScript(projectId: string, testCaseId: string): Promise<AutomationScript> {
  return api.get<AutomationScript>(`/projects/${projectId}/test-cases/${testCaseId}/automation-script`);
}

/** Generates (or regenerates) the script. */
export function generateAutomationScript(
  projectId: string,
  testCaseId: string,
  input: AutomationScriptGenerateInput,
): Promise<AutomationScript> {
  return api.post<AutomationScript>(
    `/projects/${projectId}/test-cases/${testCaseId}/automation-script`,
    input,
  );
}

export function updateAutomationScript(
  projectId: string,
  testCaseId: string,
  input: AutomationScriptUpdateInput,
): Promise<AutomationScript> {
  return api.patch<AutomationScript>(
    `/projects/${projectId}/test-cases/${testCaseId}/automation-script`,
    input,
  );
}

export function approveAutomationScript(
  projectId: string,
  testCaseId: string,
): Promise<AutomationScript> {
  return api.post<AutomationScript>(
    `/projects/${projectId}/test-cases/${testCaseId}/automation-script/approve`,
  );
}

export function listAutomationScriptVersions(
  projectId: string,
  testCaseId: string,
): Promise<ScriptVersionSummary[]> {
  return api.get<ScriptVersionSummary[]>(
    `/projects/${projectId}/test-cases/${testCaseId}/automation-script/versions`,
  );
}
