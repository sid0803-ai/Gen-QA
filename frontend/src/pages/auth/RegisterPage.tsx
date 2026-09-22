import { useState } from 'react';
import { App as AntApp, Button, Card, Form, Input, Typography } from 'antd';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/useAuth';
import { ApiError } from '../../api/client';

interface RegisterFormValues {
  full_name: string;
  email: string;
  password: string;
  confirm: string;
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const { message } = AntApp.useApp();
  const [loading, setLoading] = useState(false);

  const onFinish = async (values: RegisterFormValues) => {
    setLoading(true);
    try {
      await register(values.email, values.password, values.full_name);
      navigate('/projects', { replace: true });
    } catch (err) {
      message.error(err instanceof ApiError ? err.detail : 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f0f2f5',
      }}
    >
      <Card style={{ width: 380 }}>
        <Typography.Title level={3} style={{ textAlign: 'center', marginBottom: 4 }}>
          Gen-QA
        </Typography.Title>
        <Typography.Text
          type="secondary"
          style={{ display: 'block', textAlign: 'center', marginBottom: 24 }}
        >
          Create your account
        </Typography.Text>
        <Form<RegisterFormValues> layout="vertical" onFinish={onFinish} requiredMark={false}>
          <Form.Item
            name="full_name"
            label="Full name"
            rules={[{ required: true, message: 'Full name is required' }]}
          >
            <Input autoFocus autoComplete="name" />
          </Form.Item>
          <Form.Item
            name="email"
            label="Email"
            rules={[{ required: true, type: 'email', message: 'Enter a valid email' }]}
          >
            <Input autoComplete="username" />
          </Form.Item>
          <Form.Item
            name="password"
            label="Password"
            rules={[{ required: true, min: 8, message: 'At least 8 characters' }]}
            hasFeedback
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm"
            label="Confirm password"
            dependencies={['password']}
            hasFeedback
            rules={[
              { required: true, message: 'Please confirm your password' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('Passwords do not match'));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item style={{ marginBottom: 12 }}>
            <Button type="primary" htmlType="submit" block loading={loading}>
              Create account
            </Button>
          </Form.Item>
        </Form>
        <Typography.Text>
          Already have an account? <Link to="/login">Log in</Link>
        </Typography.Text>
      </Card>
    </div>
  );
}
