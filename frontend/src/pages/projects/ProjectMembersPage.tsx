import { useState } from 'react';
import { Alert, App as AntApp, Button, Form, Input, Modal, Popconfirm, Select, Space, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useParams } from 'react-router-dom';
import {
  useAddMember,
  useProjectMembers,
  useRemoveMember,
  useUpdateMemberRole,
} from '../../hooks/useProjectMembers';
import { useProjects } from '../../hooks/useProjects';
import { StatusBadge } from '../../components/StatusBadge';
import { useAuthStore } from '../../store/authStore';
import { ApiError } from '../../api/client';
import type { AddMemberInput, ProjectMember, Role } from '../../api/types';

const ROLE_OPTIONS: { value: Role; label: string }[] = [
  { value: 'admin', label: 'Admin' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer' },
];

export default function ProjectMembersPage() {
  const { projectId } = useParams();
  const { data: members, isLoading } = useProjectMembers(projectId);
  // GET /projects doesn't return per-member roles for other users, but it does
  // return the current user's role in each project — use that to gate admin UI.
  const { data: projects } = useProjects();
  const currentUser = useAuthStore((s) => s.user);
  const addMember = useAddMember(projectId);
  const updateRole = useUpdateMemberRole(projectId);
  const removeMember = useRemoveMember(projectId);
  const { message } = AntApp.useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm<AddMemberInput>();

  const myRole = projects?.find((p) => p.id === projectId)?.role;
  const isAdmin = myRole === 'admin';

  const handleAdd = async () => {
    try {
      const values = await form.validateFields();
      await addMember.mutateAsync(values);
      message.success('Member added');
      setModalOpen(false);
      form.resetFields();
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleRoleChange = async (userId: string, role: Role) => {
    try {
      await updateRole.mutateAsync({ userId, role });
      message.success('Role updated');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const handleRemove = async (userId: string) => {
    try {
      await removeMember.mutateAsync(userId);
      message.success('Member removed');
    } catch (err) {
      if (err instanceof ApiError) message.error(err.detail);
    }
  };

  const columns: ColumnsType<ProjectMember> = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'Full name', dataIndex: 'full_name', key: 'full_name' },
    {
      title: 'Role',
      dataIndex: 'role',
      key: 'role',
      render: (role: Role, record) =>
        isAdmin ? (
          <Select<Role>
            size="small"
            value={role}
            style={{ width: 120 }}
            options={ROLE_OPTIONS}
            disabled={record.user_id === currentUser?.id}
            onChange={(value) => handleRoleChange(record.user_id, value)}
          />
        ) : (
          <StatusBadge status={role} />
        ),
    },
  ];

  if (isAdmin) {
    columns.push({
      title: '',
      key: 'actions',
      width: 64,
      render: (_, record) => (
        <Popconfirm
          title="Remove this member?"
          disabled={record.user_id === currentUser?.id}
          onConfirm={() => handleRemove(record.user_id)}
        >
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            disabled={record.user_id === currentUser?.id}
          />
        </Popconfirm>
      ),
    });
  }

  return (
    <div>
      {!isAdmin && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="Only project admins can add, change, or remove members."
        />
      )}
      <Space style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 16 }}>
        {isAdmin && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>
            Add member
          </Button>
        )}
      </Space>
      <Table<ProjectMember>
        rowKey="user_id"
        columns={columns}
        dataSource={members ?? []}
        loading={isLoading}
      />
      {isAdmin && (
        <Modal
          title="Add member"
          open={modalOpen}
          onOk={handleAdd}
          onCancel={() => setModalOpen(false)}
          confirmLoading={addMember.isPending}
          okText="Add"
          destroyOnHidden
        >
          <Form<AddMemberInput> form={form} layout="vertical" initialValues={{ role: 'member' }}>
            <Form.Item
              name="email"
              label="Email"
              rules={[{ required: true, type: 'email', message: 'Enter a valid email' }]}
            >
              <Input />
            </Form.Item>
            <Form.Item name="role" label="Role" rules={[{ required: true }]}>
              <Select<Role> options={ROLE_OPTIONS} />
            </Form.Item>
          </Form>
        </Modal>
      )}
    </div>
  );
}
