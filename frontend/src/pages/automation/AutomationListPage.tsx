import { useMemo, useState } from 'react';
import { Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useNavigate, useParams } from 'react-router-dom';
import { useTestCases } from '../../hooks/useTestCases';
import { useAutomationScriptsByTestCase } from '../../hooks/useAutomationScript';
import { useExecutions } from '../../hooks/useExecutions';
import { StatusBadge } from '../../components/StatusBadge';
import type { AutomationScript, Execution, TestCaseSummary } from '../../api/types';

interface AutomationRow extends TestCaseSummary {
  script: AutomationScript | null | undefined;
  lastExecution: Execution | undefined;
}

const SCRIPT_STATUS_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'draft', label: 'Draft' },
  { value: 'approved', label: 'Approved' },
];

const AUTOMATION_CANDIDATE_OPTIONS = [
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
];

/**
 * Project-wide, read-mostly overview of automation status across the test
 * case repository. There's no bulk "automation scripts" endpoint in the
 * contract, so per-test-case script status is fanned out via
 * `useAutomationScriptsByTestCase` (cache-shared with the test case detail
 * page); "last execution" is derived from the single project-wide executions
 * list (already newest-first, so the first match per test case is the latest).
 */
export default function AutomationListPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { data: testCases, isLoading: testCasesLoading } = useTestCases(projectId, {});
  const testCaseIds = useMemo(() => (testCases ?? []).map((tc) => tc.id), [testCases]);
  const { map: scriptsByTestCase, isLoading: scriptsLoading } = useAutomationScriptsByTestCase(
    projectId,
    testCaseIds,
  );
  const { data: executions, isLoading: executionsLoading } = useExecutions(projectId, {});

  const [scriptStatusFilter, setScriptStatusFilter] = useState<string | undefined>();
  const [candidateFilter, setCandidateFilter] = useState<string | undefined>();

  const lastExecutionByTestCase = useMemo(() => {
    const map = new Map<string, Execution>();
    for (const execution of executions ?? []) {
      if (!map.has(execution.test_case_id)) {
        map.set(execution.test_case_id, execution);
      }
    }
    return map;
  }, [executions]);

  const rows: AutomationRow[] = useMemo(
    () =>
      (testCases ?? []).map((tc) => ({
        ...tc,
        script: scriptsByTestCase.get(tc.id),
        lastExecution: lastExecutionByTestCase.get(tc.id),
      })),
    [testCases, scriptsByTestCase, lastExecutionByTestCase],
  );

  const filteredRows = rows.filter((row) => {
    if (scriptStatusFilter) {
      const status = row.script ? row.script.status : 'none';
      if (status !== scriptStatusFilter) return false;
    }
    if (candidateFilter && String(row.automation_candidate) !== candidateFilter) return false;
    return true;
  });

  const goToTestCase = (id: string) => navigate(`/projects/${projectId}/test-cases/${id}`);

  const columns: ColumnsType<AutomationRow> = [
    { title: 'Code', dataIndex: 'code', key: 'code', width: 110 },
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record) => (
        <a onClick={() => goToTestCase(record.id)}>{title}</a>
      ),
    },
    {
      title: 'Automation candidate',
      dataIndex: 'automation_candidate',
      key: 'automation_candidate',
      width: 160,
      render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? 'Yes' : 'No'}</Tag>,
    },
    {
      title: 'Script status',
      key: 'script_status',
      width: 140,
      render: (_, record) =>
        record.script === undefined ? (
          <Typography.Text type="secondary">Loading…</Typography.Text>
        ) : record.script ? (
          <StatusBadge status={record.script.status} />
        ) : (
          <StatusBadge status="none" />
        ),
    },
    {
      title: 'Last execution',
      key: 'last_execution_status',
      width: 140,
      render: (_, record) =>
        record.lastExecution ? <StatusBadge status={record.lastExecution.status} /> : <Typography.Text type="secondary">Never run</Typography.Text>,
    },
    {
      title: 'Last run',
      key: 'last_execution_date',
      width: 160,
      render: (_, record) =>
        record.lastExecution ? new Date(record.lastExecution.created_at).toLocaleString() : '—',
    },
  ];

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Automation
      </Typography.Title>

      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="Script status"
          style={{ width: 160 }}
          value={scriptStatusFilter}
          options={SCRIPT_STATUS_OPTIONS}
          onChange={setScriptStatusFilter}
        />
        <Select
          allowClear
          placeholder="Automation candidate"
          style={{ width: 180 }}
          value={candidateFilter}
          options={AUTOMATION_CANDIDATE_OPTIONS}
          onChange={setCandidateFilter}
        />
      </Space>

      <Table<AutomationRow>
        rowKey="id"
        columns={columns}
        dataSource={filteredRows}
        loading={testCasesLoading || scriptsLoading || executionsLoading}
        locale={{ emptyText: <Typography.Text type="secondary">No test cases yet.</Typography.Text> }}
      />
    </div>
  );
}
