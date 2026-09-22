import { Button, Form, Input, Select, Space, Switch } from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { PRIORITY_OPTIONS } from '../../api/priority';
import {
  CATEGORY_OPTIONS,
  EXECUTION_TYPE_OPTIONS,
  SEVERITY_OPTIONS,
  TESTING_LEVEL_OPTIONS,
} from '../../api/testCaseOptions';

export interface RequirementOption {
  id: string;
  title: string;
}

export interface TestCaseFormFieldsProps {
  /**
   * Requirement picker — shown only on create. The contract's PATCH body
   * doesn't accept `requirement_id`, so the edit form omits it entirely
   * (a test case can't be reparented after creation).
   */
  requirementOptions?: RequirementOption[];
}

/** Shared field set for the create-test-case and edit-test-case forms/drawers. */
export function TestCaseFormFields({ requirementOptions }: TestCaseFormFieldsProps) {
  return (
    <>
      {requirementOptions && (
        <Form.Item
          name="requirement_id"
          label="Requirement"
          rules={[{ required: true, message: 'Select the requirement this test case belongs to' }]}
        >
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Select a requirement"
            options={requirementOptions.map((r) => ({ value: r.id, label: r.title }))}
          />
        </Form.Item>
      )}

      <Form.Item name="title" label="Title" rules={[{ required: true, message: 'Title is required' }]}>
        <Input autoFocus={!requirementOptions} />
      </Form.Item>

      <div style={{ display: 'flex', gap: 12 }}>
        <Form.Item name="category" label="Category" rules={[{ required: true }]} style={{ flex: 1 }}>
          <Select options={CATEGORY_OPTIONS} />
        </Form.Item>
        <Form.Item name="testing_level" label="Testing level" rules={[{ required: true }]} style={{ flex: 1 }}>
          <Select options={TESTING_LEVEL_OPTIONS} />
        </Form.Item>
      </div>

      <div style={{ display: 'flex', gap: 12 }}>
        <Form.Item name="priority" label="Priority" rules={[{ required: true }]} style={{ flex: 1 }}>
          <Select options={PRIORITY_OPTIONS} />
        </Form.Item>
        <Form.Item name="severity" label="Severity" rules={[{ required: true }]} style={{ flex: 1 }}>
          <Select options={SEVERITY_OPTIONS} />
        </Form.Item>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
        <Form.Item name="execution_type" label="Execution type" rules={[{ required: true }]} style={{ flex: 1 }}>
          <Select options={EXECUTION_TYPE_OPTIONS} />
        </Form.Item>
        <Form.Item
          name="automation_candidate"
          label="Automation candidate"
          valuePropName="checked"
          style={{ flex: 1 }}
        >
          <Switch />
        </Form.Item>
      </div>

      <Form.Item
        name="preconditions"
        label="Preconditions"
        rules={[{ required: true, message: 'Preconditions are required' }]}
      >
        <Input.TextArea rows={2} />
      </Form.Item>

      <Form.Item name="test_data" label="Test data" rules={[{ required: true, message: 'Test data is required' }]}>
        <Input.TextArea rows={2} />
      </Form.Item>

      <Form.Item label="Steps" required>
        <Form.List
          name="steps"
          rules={[
            {
              validator: async (_, steps: string[]) => {
                if (!steps || steps.length < 1) {
                  return Promise.reject(new Error('Add at least one step'));
                }
              },
            },
          ]}
        >
          {(fields, { add, remove }, { errors }) => (
            <>
              {fields.map(({ key, ...restField }) => (
                <Space key={key} align="baseline" style={{ display: 'flex', marginBottom: 8, width: '100%' }}>
                  <Form.Item
                    {...restField}
                    rules={[{ required: true, message: 'Step text is required' }]}
                    noStyle
                  >
                    <Input style={{ width: 380 }} placeholder="Step" />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(restField.name)} />
                </Space>
              ))}
              <Form.Item style={{ marginBottom: 0 }}>
                <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />}>
                  Add step
                </Button>
              </Form.Item>
              <Form.ErrorList errors={errors} />
            </>
          )}
        </Form.List>
      </Form.Item>

      <Form.Item
        name="expected_result"
        label="Expected result"
        rules={[{ required: true, message: 'Expected result is required' }]}
      >
        <Input.TextArea rows={2} />
      </Form.Item>

      <Form.Item name="business_rule" label="Business rule">
        <Input.TextArea rows={2} placeholder="Optional" />
      </Form.Item>

      <Form.Item name="tags" label="Tags">
        <Select mode="tags" placeholder="Add tags and press enter" />
      </Form.Item>
    </>
  );
}
