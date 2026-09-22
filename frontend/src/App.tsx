import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { AppLayout } from './layout/AppLayout';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import ProjectsListPage from './pages/projects/ProjectsListPage';
import ProjectDashboardPage from './pages/projects/ProjectDashboardPage';
import ProjectSettingsLayout from './pages/projects/ProjectSettingsLayout';
import ProjectMembersPage from './pages/projects/ProjectMembersPage';
import ProjectGeneralSettingsPage from './pages/projects/ProjectGeneralSettingsPage';
import RequirementsListPage from './pages/requirements/RequirementsListPage';
import RequirementDetailPage from './pages/requirements/RequirementDetailPage';
import TestCasesListPage from './pages/testcases/TestCasesListPage';
import TestCaseDetailPage from './pages/testcases/TestCaseDetailPage';
import TestPlansPage from './pages/stubs/TestPlansPage';
import AutomationPage from './pages/stubs/AutomationPage';
import TestingPage from './pages/stubs/TestingPage';
import SchedulesPage from './pages/stubs/SchedulesPage';
import ReportsPage from './pages/stubs/ReportsPage';
import NotFoundPage from './pages/NotFoundPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/projects" replace />} />
            <Route path="/projects" element={<ProjectsListPage />} />
            <Route path="/projects/:projectId" element={<ProjectDashboardPage />} />
            <Route path="/projects/:projectId/requirements" element={<RequirementsListPage />} />
            <Route
              path="/projects/:projectId/requirements/:requirementId"
              element={<RequirementDetailPage />}
            />
            <Route path="/projects/:projectId/test-cases" element={<TestCasesListPage />} />
            <Route path="/projects/:projectId/test-cases/:testCaseId" element={<TestCaseDetailPage />} />
            <Route path="/projects/:projectId/test-plans" element={<TestPlansPage />} />
            <Route path="/projects/:projectId/automation" element={<AutomationPage />} />
            <Route path="/projects/:projectId/testing" element={<TestingPage />} />
            <Route path="/projects/:projectId/schedules" element={<SchedulesPage />} />
            <Route path="/projects/:projectId/reports" element={<ReportsPage />} />
            <Route path="/projects/:projectId/settings" element={<ProjectSettingsLayout />}>
              <Route index element={<Navigate to="members" replace />} />
              <Route path="members" element={<ProjectMembersPage />} />
              <Route path="general" element={<ProjectGeneralSettingsPage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
