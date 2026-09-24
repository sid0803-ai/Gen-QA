import { useMemo, useState } from 'react';
import {
  App as AntApp,
  Button,
  Checkbox,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import { useEnvironments } from '../../hooks/useEnvironments';
import { useTestCases } from '../../hooks/useTestCases';
import { useAutomationScriptsByTestCase } from '../../hooks/useAutomationScript';
import { useCreateSchedule, useDeleteSchedule, useSchedules, useUpdateSchedule } from '../../hooks/useSchedules';
import { useProjects } from '../../hooks/useProjects';
import { ApiError } from '../../api/client';
import type { ScheduledJob, ScheduledJobCreateInput } from '../../api/types';

const { Title, Text } = Typography;

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

interface ScheduleFormValues {
  name: string;
  test_case_id: string;
  environment_id: string;
  cron_expression: string;
  enabled: boolean;
}

/**
 * Sprint 7: Scheduling. Lists a project's scheduled automated runs and lets
 * project members create/toggle/delete them. Test case + environment names
 * are resolved client-side (same "look up by id in a sibling list" pattern
 * ExecutionsSection uses for environment_id) since the ScheduledJob contract
 * only carries the ids.
 */
export default function SchedulesPage() {
  const { projectId } = useParams();
  const { message } = AntApp.useApp();

  const { data: schedules, isLoading: schedulesLoading } = useSchedules(projectId);
  const { data: environments, isLoading: environmentsLoading } = useEnvironments(projectId);
  const { data: testCases, isLoading: testCasesLoading } = useTestCases(projectId, {});
  const { data: projects } = useProjects();

  const testCaseIds = useMemo(() => (testCases ?? []).map((tc) => tc.id), [testCases]);
  const { map: scriptsByTestCase } = useAutomationScriptsByTestCase(projectId, testCaseIds);

  const createSchedule = useCreateSchedule(projectId);
  const updateSchedule = useUpdateSchedule(projectId);
  const deleteSchedule = useDeleteSchedule(projectId);

  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<ScheduleFormValues>();

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canEdit = myRole === 'admin' || myRole === 'member';

  const testCaseTitleById = useMemo(() => {
    const map = new Map<string, string>();
    for (const tc of testCases ?? []) map.set(tc.id, `${tc.code} — ${tc.title}`);
    return map;
  }, [testCases]);

  const environmentNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const env of environments ?? []) map.set(env.id, env.name);
    return map;
  }, [environments]);

  // Only test cases with an approved automation script can be scheduled — the
  // backend enforces this (400 on create otherwise), so this is a best-effort
  // client-side filter to steer users toward valid picks; the create form
  // still surfaces the API's error verbatim if something slips through
  // (e.g. the script was un-approved after the page loaded).
  const automatableTestCaseOptions = useMemo(
    () =>
      (testCases ?? [])
        .filter((tc) => scriptsByTestCase.get(tc.id)?.status === 'approved')
        .map((tc) => ({ value: tc.id, label: `${tc.code} — ${tc.title}` })),
    [testCases, scriptsByTestCase],
  );

  const openCreate = () => {
    form.resetFields();
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      const input: ScheduledJobCreateInput = {
        name: values.name,
        test_case_id: values.test_case_id,
        environment_id: values.environment_id,
        cron_expression: values.cron_expression,
        enabled: values.enabled,
      };
      await createSchedule.mutateAsync(input);
      message.success('Schedule created');
      setModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleToggleEnabled = async (schedule: ScheduledJob, enabled: boolean) => {
    try {
      await updateSchedule.mutateAsync({ id: schedule.id, input: { enabled } });
      message.success(enabled ? 'Schedule enabled' : 'Schedule disabled');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDelete = async (scheduleId: string) => {
    try {
      await deleteSchedule.mutateAsync(scheduleId);
      message.success('Schedule deleted');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<ScheduledJob> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    {
      title: 'Test case',
      dataIndex: 'test_case_id',
      key: 'test_case_id',
      render: (id: string) => testCaseTitleById.get(id) ?? id,
    },
    {
      title: 'Environment',
      dataIndex: 'environment_id',
      key: 'environment_id',
      width: 140,
      render: (id: string) => environmentNameById.get(id) ?? id,
    },
    {
      title: 'Cron expression',
      dataIndex: 'cron_expression',
      key: 'cron_expression',
      width: 150,
      render: (cron: string) => <Text code>{cron}</Text>,
    },
    {
      title: 'Enabled',
      key: 'enabled',
      width: 100,
      render: (_, record) => (
        <span data-testid={`schedule-enabled-switch-${record.id}`}>
          <Switch
            checked={record.enabled}
            disabled={!canEdit}
            loading={updateSchedule.isPending && updateSchedule.variables?.id === record.id}
            onChange={(checked) => handleToggleEnabled(record, checked)}
          />
        </span>
      ),
    },
    {
      title: 'Last run',
      dataIndex: 'last_run_at',
      key: 'last_run_at',
      width: 170,
      render: (value: string | null) => (value ? formatDateTime(value) : <Text type="secondary">Never</Text>),
    },
    {
      title: 'Next run',
      dataIndex: 'next_run_at',
      key: 'next_run_at',
      width: 170,
      render: (value: string | null) => (value ? formatDateTime(value) : <Text type="secondary">—</Text>),
    },
  ];

  if (canEdit) {
    columns.push({
      title: '',
      key: 'actions',
      width: 64,
      render: (_, record) => (
        <Popconfirm
          title="Delete this schedule?"
          okText="Delete"
          okButtonProps={{ danger: true }}
          onConfirm={() => handleDelete(record.id)}
        >
          <span data-testid={`schedule-delete-button-${record.id}`}>
            <Button
              type="text"
              danger
              icon={<DeleteOutlined />}
              loading={deleteSchedule.isPending && deleteSchedule.variables === record.id}
            />
          </span>
        </Popconfirm>
      ),
    });
  }

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>
          Schedules
        </Title>
        {canEdit && (
          <span data-testid="new-schedule-button">
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              New Schedule
            </Button>
          </span>
        )}
      </Space>

      <Table<ScheduledJob>
        rowKey="id"
        columns={columns}
        dataSource={schedules ?? []}
        loading={schedulesLoading || environmentsLoading || testCasesLoading}
        locale={{ emptyText: <Empty description="No schedules yet." /> }}
      />

      {canEdit && (
        <Modal
          title="New Schedule"
          open={modalOpen}
          onOk={handleSave}
          onCancel={() => setModalOpen(false)}
          confirmLoading={createSchedule.isPending}
          okText="Create"
          destroyOnHidden
          width={560}
        >
          <Form<ScheduleFormValues>
            form={form}
            layout="vertical"
            initialValues={{ enabled: true }}
          >
            <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Enter a name' }]}>
              <Input placeholder="Nightly regression run" data-testid="schedule-name-input" />
            </Form.Item>
            <Form.Item
              name="test_case_id"
              label="Test case"
              rules={[{ required: true, message: 'Select a test case' }]}
              extra={
                automatableTestCaseOptions.length === 0
                  ? 'No test cases with an approved automation script yet.'
                  : 'Only test cases with an approved automation script can be scheduled.'
              }
            >
              <Select
                placeholder="Select test case"
                showSearch
                optionFilterProp="label"
                options={automatableTestCaseOptions}
                data-testid="schedule-testcase-select"
              />
            </Form.Item>
            <Form.Item
              name="environment_id"
              label="Environment"
              rules={[{ required: true, message: 'Select an environment' }]}
            >
              <Select
                placeholder="Select environment"
                loading={environmentsLoading}
                options={(environments ?? []).map((e) => ({ value: e.id, label: e.name }))}
                data-testid="schedule-environment-select"
              />
            </Form.Item>
            <Form.Item
              name="cron_expression"
              label="Cron expression (5-field, e.g. 0 2 * * * = daily at 2am UTC)"
              rules={[{ required: true, message: 'Enter a cron expression' }]}
            >
              <Input placeholder="0 2 * * *" data-testid="schedule-cron-input" />
            </Form.Item>
            <Form.Item name="enabled" valuePropName="checked">
              <Checkbox data-testid="schedule-enabled-checkbox">Enabled</Checkbox>
            </Form.Item>
          </Form>
        </Modal>
      )}
    </div>
  );
}
