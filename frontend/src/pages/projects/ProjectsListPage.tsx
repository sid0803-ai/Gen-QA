import { useState } from 'react';
import { App as AntApp, Button, Form, Input, Modal, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useCreateProject, useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { useAuthStore } from '../../store/authStore';
import { ApiError } from '../../api/client';
import type { ProjectCreateInput, ProjectWithRole } from '../../api/types';

export default function ProjectsListPage() {
  const { data: projects, isLoading } = useProjects();
  const createProject = useCreateProject();
  const navigate = useNavigate();
  const setSelectedProjectId = useAuthStore((s) => s.setSelectedProjectId);
  const { message } = AntApp.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<ProjectCreateInput>();

  const openProject = (project: ProjectWithRole) => {
    setSelectedProjectId(project.id);
    navigate(`/projects/${project.id}`);
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      await createProject.mutateAsync(values);
      message.success('Project created');
      setModalOpen(false);
      form.resetFields();
    } catch (err) {
      if (err instanceof ApiError) {
        message.error(err.detail);
      }
      // form validation errors are surfaced inline by antd; nothing else to do
    }
  };

  const columns: ColumnsType<ProjectWithRole> = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record) => <a onClick={() => openProject(record)}>{name}</a>,
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (description: string | null) =>
        description || <Typography.Text type="secondary">—</Typography.Text>,
    },
    {
      title: 'Your role',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => <StatusBadge status={role} />,
    },
    {
      title: 'Created',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (createdAt: string) => new Date(createdAt).toLocaleDateString(),
    },
    {
      title: '',
      key: 'actions',
      render: (_, record) => (
        <Button type="link" onClick={() => openProject(record)}>
          Open
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Projects
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
          New Project
        </Button>
      </Space>
      <Table<ProjectWithRole>
        rowKey="id"
        columns={columns}
        dataSource={projects ?? []}
        loading={isLoading}
        locale={{ emptyText: 'No projects yet — create your first one.' }}
      />
      <Modal
        title="New Project"
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        confirmLoading={createProject.isPending}
        okText="Create"
        destroyOnHidden
      >
        <Form<ProjectCreateInput> form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Name"
            rules={[{ required: true, message: 'Project name is required' }]}
          >
            <Input autoFocus />
          </Form.Item>
          <Form.Item name="description" label="Description">
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
