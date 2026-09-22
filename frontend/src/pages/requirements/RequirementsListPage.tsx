import { useState } from 'react';
import { App as AntApp, Button, Empty, Form, Modal, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useCreateRequirement, useRequirements } from '../../hooks/useRequirements';
import { useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { ApiError } from '../../api/client';
import type { Priority, RequirementCreateInput, RequirementSummary } from '../../api/types';
import { RequirementFormFields } from './RequirementFormFields';

export default function RequirementsListPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const { data: requirements, isLoading } = useRequirements(projectId);
  const { data: projects } = useProjects();
  const createRequirement = useCreateRequirement(projectId);
  const { message } = AntApp.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<RequirementCreateInput>();

  // Same pattern as ProjectMembersPage: GET /projects returns the current
  // user's role per project, so gate create/edit controls off that.
  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canCreate = myRole === 'admin' || myRole === 'member';

  const goToRequirement = (id: string) => navigate(`/projects/${projectId}/requirements/${id}`);

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const created = await createRequirement.mutateAsync(values);
      message.success('Requirement created');
      setModalOpen(false);
      form.resetFields();
      goToRequirement(created.id);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<RequirementSummary> = [
    {
      title: 'Title',
      dataIndex: 'title',
      key: 'title',
      render: (title: string, record) => (
        <a
          onClick={(e) => {
            e.stopPropagation();
            goToRequirement(record.id);
          }}
        >
          {title}
        </a>
      ),
    },
    {
      title: 'Priority',
      dataIndex: 'priority',
      key: 'priority',
      width: 120,
      render: (priority: Priority) => <StatusBadge status={priority} />,
    },
    {
      title: 'Analysis',
      dataIndex: 'latest_analysis_status',
      key: 'latest_analysis_status',
      width: 140,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: 'Feasibility',
      dataIndex: 'latest_feasibility_status',
      key: 'latest_feasibility_status',
      width: 140,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: 'Strategy',
      dataIndex: 'latest_strategy_status',
      key: 'latest_strategy_status',
      width: 140,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (createdAt: string) => new Date(createdAt).toLocaleDateString(),
    },
  ];

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Requirements
        </Typography.Title>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            New Requirement
          </Button>
        )}
      </Space>
      <Table<RequirementSummary>
        rowKey="id"
        columns={columns}
        dataSource={requirements ?? []}
        loading={isLoading}
        onRow={(record) => ({
          onClick: () => goToRequirement(record.id),
          style: { cursor: 'pointer' },
        })}
        locale={{
          emptyText: (
            <Empty
              description={
                canCreate ? 'No requirements yet — create your first one.' : 'No requirements yet.'
              }
            />
          ),
        }}
      />
      {canCreate && (
        <Modal
          title="New Requirement"
          open={modalOpen}
          onOk={handleCreate}
          onCancel={() => setModalOpen(false)}
          confirmLoading={createRequirement.isPending}
          okText="Create"
          destroyOnHidden
          width={640}
        >
          <Form<RequirementCreateInput> form={form} layout="vertical" initialValues={{ priority: 'medium' }}>
            <RequirementFormFields />
          </Form>
        </Modal>
      )}
    </div>
  );
}
