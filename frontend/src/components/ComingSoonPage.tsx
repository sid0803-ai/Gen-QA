import { Result } from 'antd';
import { ToolOutlined } from '@ant-design/icons';

export interface ComingSoonPageProps {
  title: string;
  phase: string;
}

/** Generic placeholder used by every nav item that has no Sprint 1 functionality yet. */
export function ComingSoonPage({ title, phase }: ComingSoonPageProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
      }}
    >
      <Result
        icon={<ToolOutlined />}
        title={title}
        subTitle={`Coming soon — ${phase}`}
      />
    </div>
  );
}
