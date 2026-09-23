import { useState } from 'react';
import { Alert, App as AntApp, Button, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import {
  useCreateEnvironment,
  useDeleteEnvironment,
  useEnvironments,
  useUpdateEnvironment,
} from '../../hooks/useEnvironments';
import { useProjects } from '../../hooks/useProjects';
import { KeyValueListEditor } from '../../components/KeyValueListEditor';
import { ApiError } from '../../api/client';
import type { Environment, EnvironmentCreateInput } from '../../api/types';

const { Text } = Typography;

export default function ProjectEnvironmentsPage() {
  const { projectId } = useParams();
  const { data: environments, isLoading } = useEnvironments(projectId);
  const { data: projects } = useProjects();
  const createEnvironment = useCreateEnvironment(projectId);
  const updateEnvironment = useUpdateEnvironment(projectId);
  const deleteEnvironment = useDeleteEnvironment(projectId);
  const { message } = AntApp.useApp();

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Environment | null>(null);
  const [form] = Form.useForm<EnvironmentCreateInput>();

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const canEdit = myRole === 'admin' || myRole === 'member';
  const isAdmin = myRole === 'admin';

  const openCreate = () => {
    setEditing(null);
    setModalOpen(true);
  };

  const openEdit = (env: Environment) => {
    setEditing(env);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (editing) {
        await updateEnvironment.mutateAsync({ id: editing.id, input: values });
        message.success('Environment updated');
      } else {
        await createEnvironment.mutateAsync(values);
        message.success('Environment created');
      }
      setModalOpen(false);
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteEnvironment.mutateAsync(id);
      message.success('Environment deleted');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<Environment> = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Base URL', dataIndex: 'base_url', key: 'base_url' },
    {
      title: 'Variables',
      key: 'variables',
      width: 140,
      render: (_, record) => <Tag>{Object.keys(record.variables ?? {}).length} variable(s)</Tag>,
    },
  ];

  if (canEdit) {
    columns.push({
      title: '',
      key: 'actions',
      width: 96,
      render: (_, record) => (
        <Space>
          <Button type="text" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          {isAdmin && (
            <Popconfirm title="Delete this environment?" onConfirm={() => handleDelete(record.id)}>
              <Button type="text" danger icon={<DeleteOutlined />} loading={deleteEnvironment.isPending} />
            </Popconfirm>
          )}
        </Space>
      ),
    });
  }

  return (
    <div>
      {!canEdit && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Only project members and admins can manage environments."
        />
      )}
      <Space style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        {canEdit && (
          <span data-testid="new-environment-button">
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              New Environment
            </Button>
          </span>
        )}
      </Space>
      <Table<Environment>
        rowKey="id"
        columns={columns}
        dataSource={environments ?? []}
        loading={isLoading}
        locale={{ emptyText: <Text type="secondary">No environments yet.</Text> }}
      />
      {canEdit && (
        <Modal
          title={editing ? 'Edit Environment' : 'New Environment'}
          open={modalOpen}
          onOk={handleSave}
          onCancel={() => setModalOpen(false)}
          confirmLoading={createEnvironment.isPending || updateEnvironment.isPending}
          okText="Save"
          destroyOnHidden
          width={560}
        >
          <Form<EnvironmentCreateInput>
            form={form}
            layout="vertical"
            initialValues={
              editing
                ? { name: editing.name, base_url: editing.base_url, variables: editing.variables }
                : undefined
            }
          >
            <Form.Item name="name" label="Name" rules={[{ required: true, message: 'Enter a name' }]}>
              <Input placeholder="Staging" />
            </Form.Item>
            <Form.Item
              name="base_url"
              label="Base URL"
              rules={[{ required: true, message: 'Enter a base URL' }]}
            >
              <Input placeholder="https://staging.example.com" />
            </Form.Item>
            <Form.Item name="variables" label="Variables">
              <KeyValueListEditor />
            </Form.Item>
          </Form>
        </Modal>
      )}
    </div>
  );
}
