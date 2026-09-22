import { Button, Result } from 'antd';
import { useNavigate } from 'react-router-dom';

export default function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
      }}
    >
      <Result
        status="404"
        title="404"
        subTitle="Sorry, that page doesn't exist."
        extra={
          <Button type="primary" onClick={() => navigate('/projects')}>
            Back to Projects
          </Button>
        }
      />
    </div>
  );
}
