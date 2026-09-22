import { Form, Input, Select } from 'antd';
import { PRIORITY_OPTIONS } from '../../api/priority';

/** Shared field set for the create-requirement and edit-requirement forms. */
export function RequirementFormFields() {
  return (
    <>
      <Form.Item name="title" label="Title" rules={[{ required: true, message: 'Title is required' }]}>
        <Input autoFocus />
      </Form.Item>
      <Form.Item
        name="description"
        label="Description"
        rules={[{ required: true, message: 'Description is required' }]}
      >
        <Input.TextArea rows={4} />
      </Form.Item>
      <Form.Item name="business_objective" label="Business objective">
        <Input.TextArea rows={2} placeholder="Optional" />
      </Form.Item>
      <Form.Item name="acceptance_criteria" label="Acceptance criteria">
        <Input.TextArea rows={2} placeholder="Optional" />
      </Form.Item>
      <Form.Item name="priority" label="Priority" rules={[{ required: true }]}>
        <Select options={PRIORITY_OPTIONS} />
      </Form.Item>
    </>
  );
}
